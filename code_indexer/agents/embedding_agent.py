"""
Embedding Agent

This agent generates vector embeddings for code chunks.
"""

import logging
import time
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

from google.adk import Agent, AgentContext
from google.adk.agents.llm_agent import BaseTool

from code_indexer.tools.embedding_tool import EmbeddingTool


class EmbeddingAgent(Agent):
    """
    Agent responsible for generating vector embeddings for code chunks.
    
    This agent takes code chunks from the ChunkerAgent and generates vector
    embeddings using the EmbeddingTool, preparing them for storage and search.
    """
    
    def __init__(self):
        """Initialize the Embedding Agent."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Default batch size
        self.batch_size = 10
    
    def initialize(self, context: AgentContext) -> None:
        """
        Initialize the agent with necessary tools and state.
        
        Args:
            context: The agent context
        """
        self.context = context
        
        # Initialize the embedding tool
        self.embedding_tool = EmbeddingTool()
        
        # Load configuration if provided
        config = context.state.get("config", {}).get("embedding", {})
        if config:
            self.batch_size = config.get("batch_size", self.batch_size)
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate embeddings for code chunks.
        
        Args:
            inputs: Dictionary with code chunks from the ChunkerAgent
            
        Returns:
            Dictionary with embeddings and their metadata
        """
        # Extract inputs
        chunks = inputs.get("chunks", [])
        
        if not chunks:
            self.logger.warning("No chunks provided for embedding")
            return {"embeddings": [], "count": 0}
        
        # Track progress and results
        embeddings = []
        successful = 0
        failed = 0
        
        # Process chunks in batches for efficiency
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i+self.batch_size]
            
            # Prepare texts for embedding
            texts = []
            for chunk in batch:
                # Format the text based on content type
                formatted_text = self._format_chunk_for_embedding(chunk)
                texts.append(formatted_text)
            
            # Generate embeddings for batch
            try:
                start_time = time.time()
                batch_embeddings = self.embedding_tool.embed_texts(texts)
                embedding_time = time.time() - start_time
                
                # Combine embeddings with chunk metadata
                for j, embedding in enumerate(batch_embeddings):
                    chunk = batch[j]
                    
                    # Add embedding to result
                    embeddings.append({
                        "chunk_id": chunk["chunk_id"],
                        "entity_id": chunk["entity_id"],
                        "entity_type": chunk["entity_type"],
                        "file_id": chunk["file_id"],
                        "file_path": chunk["file_path"],
                        "language": chunk["language"],
                        "start_line": chunk["start_line"],
                        "end_line": chunk["end_line"],
                        "content_type": chunk["content_type"],
                        "vector": embedding
                    })
                    
                    successful += 1
                
                self.logger.info(f"Generated {len(batch_embeddings)} embeddings "
                                f"in {embedding_time:.2f}s")
                
            except Exception as e:
                self.logger.error(f"Error generating embeddings for batch: {e}")
                failed += len(batch)
        
        # Return results
        return {
            "embeddings": embeddings,
            "count": len(embeddings),
            "successful": successful,
            "failed": failed
        }
    
    def _format_chunk_for_embedding(self, chunk: Dict[str, Any]) -> str:
        """
        Format a code chunk for optimal embedding.
        
        Args:
            chunk: Chunk data with content and metadata
            
        Returns:
            Formatted text for embedding
        """
        content = chunk.get("content", "")
        language = chunk.get("language", "unknown")
        content_type = chunk.get("content_type", "window")
        file_path = chunk.get("file_path", "")
        
        # Format based on content type
        if content_type == "class":
            class_name = ""
            for line in content.splitlines():
                if "class " in line and ":" in line:
                    class_name = line.split("class ")[1].split("(")[0].split(":")[0].strip()
                    break
            
            formatted = f"LANGUAGE: {language}\nFILE: {file_path}\nTYPE: class\n"
            if class_name:
                formatted += f"CLASS: {class_name}\n"
            formatted += f"\n{content}"
            
        elif content_type == "function":
            func_name = ""
            for line in content.splitlines():
                if ("def " in line or "function " in line) and "(" in line:
                    if "def " in line:
                        func_name = line.split("def ")[1].split("(")[0].strip()
                    else:
                        func_name = line.split("function ")[1].split("(")[0].strip()
                    break
            
            formatted = f"LANGUAGE: {language}\nFILE: {file_path}\nTYPE: function\n"
            if func_name:
                formatted += f"FUNCTION: {func_name}\n"
            formatted += f"\n{content}"
            
        elif content_type == "header":
            formatted = f"LANGUAGE: {language}\nFILE: {file_path}\nTYPE: header\n\n{content}"
            
        else:  # window or unknown
            formatted = f"LANGUAGE: {language}\nFILE: {file_path}\nTYPE: code\n\n{content}"
        
        return formatted