"""
Vector Store Factory

Factory for creating vector store instances.
"""

import logging
from typing import Dict, Any, Optional

from code_indexer.tools.vector_store_interface import VectorStoreInterface

# Import implementations conditionally to handle missing dependencies
try:
    from code_indexer.tools.milvus_vector_store import MilvusVectorStore
    HAS_MILVUS = True
except ImportError:
    HAS_MILVUS = False
    logging.warning("Milvus support not available. Install pymilvus package to enable it.")

try:
    from code_indexer.tools.qdrant_vector_store import QdrantVectorStore
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False
    logging.warning("Qdrant support not available. Install qdrant-client package to enable it.")


class VectorStoreFactory:
    """
    Factory for creating vector store instances.
    
    This class provides a method to create the appropriate vector store
    implementation based on configuration.
    """
    
    @staticmethod
    def create_vector_store(config: Dict[str, Any]) -> VectorStoreInterface:
        """
        Create a vector store instance based on configuration.
        
        Args:
            config: Configuration dictionary with vector store settings
            
        Returns:
            Vector store implementation instance
            
        Raises:
            ValueError: If the specified vector store type is not supported
            ImportError: If the required dependencies are not installed
        """
        store_type = config.get("type", "").lower()
        
        if store_type == "milvus":
            if not HAS_MILVUS:
                raise ImportError("Milvus support requires pymilvus package")
            
            # Import here to avoid circular import
            from code_indexer.tools.milvus_vector_store import MilvusVectorStore
            return MilvusVectorStore(config.get("milvus", {}))
            
        elif store_type == "qdrant":
            if not HAS_QDRANT:
                raise ImportError("Qdrant support requires qdrant-client package")
            
            # Import here to avoid circular import
            from code_indexer.tools.qdrant_vector_store import QdrantVectorStore
            return QdrantVectorStore(config.get("qdrant", {}))
            
        else:
            raise ValueError(f"Unsupported vector store type: {store_type}. "
                           f"Supported types: milvus, qdrant")
    
    @staticmethod
    def available_stores() -> Dict[str, bool]:
        """
        Get available vector store implementations.
        
        Returns:
            Dictionary mapping store types to availability status
        """
        return {
            "milvus": HAS_MILVUS,
            "qdrant": HAS_QDRANT
        }