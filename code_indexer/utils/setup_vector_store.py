"""
Utility script to set up the vector store.

This script initializes the vector store collections on startup.
"""

import os
import sys
import logging
from typing import Dict, Any

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from code_indexer.tools.vector_store_factory import VectorStoreFactory
from code_indexer.utils.vector_store_utils import load_vector_store_config


def setup_vector_store():
    """Set up the vector store with necessary collections."""
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_vector_store_config()
        
        # Get vector store type from environment or config
        vector_store_type = os.environ.get("VECTOR_STORE", config.get("default", {}).get("type", "milvus"))
        logger.info(f"Setting up {vector_store_type} vector store")
        
        # Create vector store instance
        vector_store = VectorStoreFactory.create_vector_store({
            "type": vector_store_type,
            "config": config.get(vector_store_type, {})
        })
        
        # Connect to the vector store
        if not vector_store.connect():
            logger.error("Failed to connect to vector store")
            return False
        
        # Set up default collection
        default_collection = os.environ.get("DEFAULT_COLLECTION", "code_embeddings")
        embedding_dimension = int(os.environ.get("EMBEDDING_DIMENSION", "384"))
        
        # Create metadata schema
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
        
        # Check if collection exists and create if needed
        if not vector_store.collection_exists(default_collection):
            logger.info(f"Creating collection: {default_collection}")
            vector_store.create_collection(
                name=default_collection,
                dimension=embedding_dimension,
                metadata_schema=metadata_schema
            )
            logger.info(f"Collection {default_collection} created successfully")
        else:
            logger.info(f"Collection {default_collection} already exists")
        
        # Create index if needed
        logger.info(f"Creating index on collection {default_collection}")
        vector_store.create_index(
            collection=default_collection,
            field="vector", 
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 1024}
        )
        
        # Disconnect from vector store
        vector_store.disconnect()
        logger.info("Vector store setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error setting up vector store: {e}")
        return False


if __name__ == "__main__":
    setup_vector_store()