"""
Vector Store Agent

This agent manages the storage and retrieval of code embeddings.
"""

import logging
import time
import numpy as np
from typing import Dict, List, Any, Optional, Union

from google.adk import Agent, AgentSpec
from google.adk.runtime.context import AgentContext
from google.adk.runtime.responses import HandlerResponse, ToolResponse, ToolStatus
from google.adk.agents.llm_agent import BaseTool

from code_indexer.tools.vector_store_factory import VectorStoreFactory
from code_indexer.tools.vector_store_interface import VectorStoreInterface


class VectorStoreAgent(Agent):
    """
    Agent responsible for managing code embeddings in the vector store.
    
    This agent stores embeddings from the EmbeddingAgent and provides
    search functionality to find semantically similar code.
    """
    
    def __init__(self, name: str = "vector_store_agent", **kwargs):
        """
        Initialize the Vector Store Agent.
        
        Args:
            name: Agent name
            **kwargs: Additional parameters including config
        """
        super().__init__(name=name)
        self.logger = logging.getLogger(name)
        self.vector_store = None
        
        # Default configuration
        self.default_collection = "code_embeddings"
        self.embedding_dimension = 1536  # Default for most embedding models
        self.batch_size = 100
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with necessary tools and state.
        
        Args:
            context: The agent context
        """
        self.context = context
        
        # Load vector store configuration
        vector_store_config = context.state.get("config", {}).get("vector_store", {})
        
        # Create vector store instance
        self.vector_store = VectorStoreFactory.create_vector_store(vector_store_config)
        
        # Get configuration values
        if vector_store_config:
            self.default_collection = vector_store_config.get(
                "default_collection", self.default_collection
            )
            self.embedding_dimension = vector_store_config.get(
                "embedding_dimension", self.embedding_dimension
            )
            self.batch_size = vector_store_config.get(
                "batch_size", self.batch_size
            )
        
        # Connect to vector store
        self.vector_store.connect()
        
        # Create default collection if it doesn't exist
        if not self.vector_store.collection_exists(self.default_collection):
            self._create_default_collection()
    
    def run(self, inputs: Dict[str, Any]) -> HandlerResponse:
        """
        Store or search embeddings in the vector store.
        
        Args:
            inputs: Dictionary with operation type and data
            
        Returns:
            HandlerResponse with operation results
        """
        # Extract operation type
        operation = inputs.get("operation", "store")
        
        if operation == "store":
            result = self._handle_store(inputs)
            return HandlerResponse.success(result) if result.get("status") == "success" else HandlerResponse.error(result.get("message", "Store operation failed"))
        elif operation == "search":
            result = self._handle_search(inputs)
            return HandlerResponse.success(result) if result.get("status") == "success" else HandlerResponse.error(result.get("message", "Search operation failed"))
        elif operation == "delete":
            result = self._handle_delete(inputs)
            return HandlerResponse.success(result) if result.get("status") == "success" else HandlerResponse.error(result.get("message", "Delete operation failed"))
        else:
            self.logger.warning(f"Unknown operation: {operation}")
            return HandlerResponse.error(f"Unknown operation: {operation}")
    
    def _handle_store(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store embeddings in the vector store.
        
        Args:
            inputs: Dictionary with embeddings from the EmbeddingAgent
            
        Returns:
            Dictionary with storage results
        """
        # Extract inputs
        embeddings = inputs.get("embeddings", [])
        collection = inputs.get("collection", self.default_collection)
        
        if not embeddings:
            self.logger.warning("No embeddings provided for storage")
            return {"stored": 0, "status": "error", "message": "No embeddings provided"}
        
        # Track progress
        stored_count = 0
        failed_count = 0
        ids = []
        
        # Process embeddings in batches
        for i in range(0, len(embeddings), self.batch_size):
            batch = embeddings[i:i+self.batch_size]
            
            # Prepare vectors and metadata
            vectors = []
            metadata = []
            chunk_ids = []
            
            for emb in batch:
                # Extract vector
                vector = emb.get("vector")
                if not isinstance(vector, (list, np.ndarray)):
                    failed_count += 1
                    continue
                
                # Convert numpy array to list if needed
                if isinstance(vector, np.ndarray):
                    vector = vector.tolist()
                
                vectors.append(vector)
                
                # Prepare metadata (everything except the vector)
                meta = {k: v for k, v in emb.items() if k != "vector"}
                metadata.append(meta)
                
                # Use chunk_id as the ID
                chunk_ids.append(emb.get("chunk_id"))
            
            # Store batch in vector store
            try:
                batch_ids = self.vector_store.insert(
                    collection=collection,
                    vectors=vectors,
                    metadata=metadata,
                    ids=chunk_ids
                )
                
                ids.extend(batch_ids)
                stored_count += len(batch_ids)
                
                self.logger.info(f"Stored {len(batch_ids)} embeddings in {collection}")
                
            except Exception as e:
                self.logger.error(f"Error storing embeddings batch: {e}")
                failed_count += len(vectors)
        
        # Return results
        return {
            "stored": stored_count,
            "failed": failed_count,
            "ids": ids,
            "collection": collection,
            "status": "success" if stored_count > 0 else "error"
        }
    
    def _handle_search(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search for similar vectors in the vector store.
        
        Args:
            inputs: Dictionary with query vector and search parameters
            
        Returns:
            Dictionary with search results
        """
        # Extract inputs
        query_vector = inputs.get("query_vector")
        collection = inputs.get("collection", self.default_collection)
        top_k = inputs.get("top_k", 10)
        filters = inputs.get("filters")
        
        if query_vector is None:
            self.logger.warning("No query vector provided for search")
            return {"results": [], "status": "error", "message": "No query vector provided"}
        
        # Convert numpy array to list if needed
        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()
        
        # Search vector store
        try:
            results = self.vector_store.search(
                collection=collection,
                query_vectors=[query_vector],
                top_k=top_k,
                filters=filters
            )
            
            # Process results to ensure they're JSON serializable
            processed_results = []
            for result in results:
                # Convert numpy arrays to lists
                if hasattr(result, "to_dict"):
                    result_dict = result.to_dict()
                else:
                    result_dict = {
                        "id": result.get("id", ""),
                        "score": float(result.get("score", 0.0)),
                        "metadata": result.get("metadata", {})
                    }
                
                processed_results.append(result_dict)
            
            self.logger.info(f"Found {len(processed_results)} results for search")
            
            return {
                "results": processed_results,
                "count": len(processed_results),
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error searching embeddings: {e}")
            return {"results": [], "status": "error", "message": str(e)}
    
    def _handle_delete(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete embeddings from the vector store.
        
        Args:
            inputs: Dictionary with deletion criteria
            
        Returns:
            Dictionary with deletion results
        """
        # Extract inputs
        collection = inputs.get("collection", self.default_collection)
        ids = inputs.get("ids")
        filters = inputs.get("filters")
        
        if not ids and not filters:
            self.logger.warning("No IDs or filters provided for deletion")
            return {"deleted": 0, "status": "error", "message": "No deletion criteria provided"}
        
        # Delete from vector store
        try:
            deleted_count = self.vector_store.delete(
                collection=collection,
                ids=ids,
                filters=filters
            )
            
            self.logger.info(f"Deleted {deleted_count} embeddings from {collection}")
            
            return {
                "deleted": deleted_count,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error deleting embeddings: {e}")
            return {"deleted": 0, "status": "error", "message": str(e)}
    
    def _create_default_collection(self) -> None:
        """Create the default collection with appropriate schema."""
        try:
            metadata_schema = {
                "file_path": "string",
                "language": "string",
                "entity_type": "string",
                "entity_id": "string",
                "file_id": "string",
                "start_line": "int",
                "end_line": "int",
                "content_type": "string",
                "chunk_id": "string"
            }
            
            self.vector_store.create_collection(
                name=self.default_collection,
                dimension=self.embedding_dimension,
                metadata_schema=metadata_schema
            )
            
            self.logger.info(f"Created collection: {self.default_collection}")
            
        except Exception as e:
            self.logger.error(f"Error creating collection: {e}")
    
    def __del__(self):
        """Clean up resources when agent is destroyed."""
        if self.vector_store:
            self.vector_store.disconnect()
            
    @classmethod
    def build_spec(cls, name: str = "vector_store_agent") -> AgentSpec:
        """
        Build the agent specification.
        
        Args:
            name: Name of the agent
            
        Returns:
            Agent specification
        """
        return AgentSpec(
            name=name,
            description="Agent responsible for managing code embeddings in the vector store",
            agent_class=cls,
        )

# Create the agent specification
spec = VectorStoreAgent.build_spec(name="vector_store_agent")