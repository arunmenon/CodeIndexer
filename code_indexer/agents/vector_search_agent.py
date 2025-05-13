"""
Vector Search Agent

Agent responsible for performing vector similarity search on code embeddings.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Union

from code_indexer.agents.adk_adapter import Agent, AgentContext, HandlerResponse, ToolResponse, init_agent

@init_agent(name="vector_search_agent")
class VectorSearchAgent(Agent):
    """
    Agent responsible for performing vector similarity search on code embeddings.
    
    This agent takes query embeddings and performs similarity search against
    the vector store to find code snippets that are semantically similar to
    the query.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the vector search agent.
        
        Args:
            config: Configuration dictionary
        """
        # The Agent initialization is handled by the decorator
        # This method is not directly called - wrapper setup is done in init_wrapper
        pass
    
    def init_wrapper(self, wrapper, config: Dict[str, Any], *args, **kwargs):
        """
        Initialize the wrapper with agent state.
        
        Args:
            wrapper: Agent wrapper instance
            config: Configuration dictionary
        """
        # Store the configuration
        wrapper.config = config
        
        # Configure defaults
        wrapper.default_collection = config.get("default_collection", "code_embeddings")
        wrapper.default_top_k = config.get("default_top_k", 10)
        wrapper.minimum_score = config.get("minimum_score", 0.7)  # Minimum similarity score (0-1)
        wrapper.reranking_enabled = config.get("reranking_enabled", True)
        
        # Available tools
        wrapper.vector_store_agent = None
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        # Get wrapper for this agent
        wrapper = self.get_wrapper()
        wrapper.context = context
        
        # Get vector store agent
        tool_response = context.get_tool("vector_store_agent")
        if tool_response.status.is_success():
            wrapper.vector_store_agent = tool_response.tool
            wrapper.logger.info("Successfully acquired vector store agent")
        else:
            wrapper.logger.error("Failed to acquire vector store agent: %s", 
                                tool_response.status.message)
    
    def run(self, wrapper, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Perform vector search for a query.
        
        Args:
            wrapper: Agent wrapper with state
            input_data: Dictionary containing search parameters
            
        Returns:
            HandlerResponse with search results
        """
        wrapper.logger.info("Performing vector search")
        
        # Extract search specification
        search_spec = input_data.get("search_spec", {})
        if not search_spec:
            return HandlerResponse.error("No search specification provided")
        
        # Extract query embeddings
        embeddings = search_spec.get("embeddings", {})
        primary_embedding = embeddings.get("primary", [])
        expanded_embeddings = embeddings.get("expanded", [])
        
        if not primary_embedding:
            return HandlerResponse.error("No query embedding provided")
        
        # Extract search parameters
        collection = input_data.get("collection", wrapper.default_collection)
        top_k = input_data.get("max_results", wrapper.default_top_k)
        filters = search_spec.get("filters", {})
        
        # Perform primary search
        primary_results = self._perform_search(
            wrapper=wrapper,
            collection=collection,
            embedding=primary_embedding,
            top_k=top_k,
            filters=filters
        )
        
        # Perform expanded searches if available
        expanded_results = []
        for expanded in expanded_embeddings:
            expanded_query = expanded.get("query", "")
            expanded_embedding = expanded.get("embedding", [])
            
            if expanded_embedding:
                results = self._perform_search(
                    wrapper=wrapper,
                    collection=collection,
                    embedding=expanded_embedding,
                    top_k=top_k // 2,  # Fewer results for expanded queries
                    filters=filters
                )
                
                if results:
                    expanded_results.append({
                        "query": expanded_query,
                        "results": results
                    })
        
        # Merge and rerank results if needed
        if wrapper.reranking_enabled and expanded_results:
            all_results = self._merge_and_rerank(wrapper, primary_results, expanded_results)
        else:
            all_results = primary_results
        
        # Filter results based on minimum score
        filtered_results = [r for r in all_results if r["score"] >= wrapper.minimum_score]
        
        # Process results to include text content
        processed_results = self._process_results(wrapper, filtered_results)
        
        wrapper.logger.info(f"Vector search completed: {len(processed_results)} results found")
        return HandlerResponse.success({
            "results": processed_results,
            "total_count": len(processed_results),
            "original_count": len(all_results),
            "collection": collection
        })
    
    def _perform_search(self, wrapper, collection: str, embedding: List[float], top_k: int, 
                      filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform a single vector search.
        
        Args:
            wrapper: Agent wrapper with state
            collection: Vector store collection
            embedding: Query embedding
            top_k: Number of results to return
            filters: Filters to apply
            
        Returns:
            List of search results
        """
        if not wrapper.vector_store_agent:
            wrapper.logger.error("Vector store agent not available")
            return []
        
        try:
            # Prepare search parameters
            search_params = {
                "collection": collection,
                "query_embedding": embedding,
                "top_k": top_k,
                "filters": filters
            }
            
            # Call the vector store agent to perform the search
            tool_response = wrapper.vector_store_agent.search(search_params)
            
            if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                results = tool_response.data.get("results", [])
                
                # Normalize results format
                normalized_results = []
                for result in results:
                    normalized_results.append({
                        "id": result.get("id"),
                        "score": result.get("score", 0.0),
                        "metadata": result.get("metadata", {}),
                        "source": "primary"
                    })
                
                return normalized_results
            else:
                wrapper.logger.error(f"Vector search failed: {tool_response.status.message if isinstance(tool_response, ToolResponse) else 'Unknown error'}")
                return []
        except Exception as e:
            wrapper.logger.error(f"Error performing vector search: {e}")
            return []
    
    def _merge_and_rerank(self, wrapper, primary_results: List[Dict[str, Any]], 
                        expanded_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge and rerank results from primary and expanded searches.
        
        Args:
            wrapper: Agent wrapper with state
            primary_results: Results from primary query
            expanded_results: Results from expanded queries
            
        Returns:
            Merged and reranked results
        """
        # Track seen IDs to avoid duplicates
        seen_ids = set()
        
        # Start with primary results
        merged_results = []
        for result in primary_results:
            result_id = result["id"]
            seen_ids.add(result_id)
            merged_results.append(result)
        
        # Add unique results from expanded queries
        for expanded in expanded_results:
            expanded_query_results = expanded.get("results", [])
            for result in expanded_query_results:
                result_id = result["id"]
                if result_id not in seen_ids:
                    seen_ids.add(result_id)
                    result["source"] = "expanded"
                    merged_results.append(result)
        
        # Apply reranking
        reranked_results = self._rerank_results(wrapper, merged_results)
        
        return reranked_results
    
    def _rerank_results(self, wrapper, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank results based on custom criteria.
        
        Args:
            wrapper: Agent wrapper with state
            results: List of search results
            
        Returns:
            Reranked results
        """
        # In a real implementation, this would use a more sophisticated reranking approach
        # For now, just apply some simple adjustments
        
        reranked = results.copy()
        
        # Apply boosting based on metadata
        for result in reranked:
            score = result["score"]
            metadata = result["metadata"]
            
            # Boost functions and classes slightly
            if metadata.get("entity_type") in ["function", "class"]:
                score *= 1.05
            
            # Penalty for very short snippets
            if metadata.get("end_line", 0) - metadata.get("start_line", 0) < 3:
                score *= 0.95
            
            # Use source information for scoring
            if result.get("source") == "expanded":
                score *= 0.98  # Slight penalty for expanded results
            
            # Update the score
            result["score"] = min(score, 1.0)  # Cap at 1.0
        
        # Sort by score descending
        reranked.sort(key=lambda x: x["score"], reverse=True)
        
        return reranked
    
    def _process_results(self, wrapper, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process results to include text content and additional metadata.
        
        Args:
            wrapper: Agent wrapper with state
            results: Vector search results
            
        Returns:
            Processed results with code content
        """
        processed_results = []
        
        for result in results:
            # Extract metadata
            metadata = result.get("metadata", {})
            chunk_id = metadata.get("chunk_id", "")
            
            # In a real implementation, we would fetch the actual code content
            # For now, just include placeholder content
            
            processed_result = {
                "id": result.get("id"),
                "score": result.get("score"),
                "file_path": metadata.get("file_path", ""),
                "language": metadata.get("language", ""),
                "entity_type": metadata.get("entity_type", ""),
                "entity_id": metadata.get("entity_id", ""),
                "start_line": metadata.get("start_line", 0),
                "end_line": metadata.get("end_line", 0),
                "code_content": self._get_code_content(wrapper, metadata),
                "metadata": metadata
            }
            
            processed_results.append(processed_result)
        
        return processed_results
    
    def _get_code_content(self, wrapper, metadata: Dict[str, Any]) -> str:
        """
        Get code content from metadata.
        
        In a real implementation, this would fetch the code content from the
        repository or a content cache.
        
        Args:
            wrapper: Agent wrapper with state
            metadata: Result metadata
            
        Returns:
            Code content
        """
        # This is a placeholder implementation
        file_path = metadata.get("file_path", "")
        entity_type = metadata.get("entity_type", "")
        entity_id = metadata.get("entity_id", "")
        language = metadata.get("language", "")
        
        # In a real implementation, we would fetch the actual code
        # For now, return placeholder content
        if entity_type == "function":
            return f"def {entity_id}():\n    # Function content would appear here\n    pass"
        elif entity_type == "class":
            return f"class {entity_id}:\n    # Class content would appear here\n    pass"
        elif entity_type == "method":
            return f"def {entity_id}(self):\n    # Method content would appear here\n    pass"
        else:
            return "# Code content would appear here"