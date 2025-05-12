"""
Milvus Vector Store Example

This script demonstrates basic operations with the MilvusVectorStore implementation.
To run this example, you need to have Milvus running. You can use the docker-compose.milvus.yml
file to start a Milvus instance:

    docker-compose -f docker-compose.milvus.yml up -d

Requirements:
- pymilvus
- numpy
"""

import os
import sys
import logging
import uuid
import numpy as np
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path to allow importing code_indexer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_indexer.tools.vector_store_factory import VectorStoreFactory
from code_indexer.utils.vector_store_utils import FilterBuilder, format_code_metadata


# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("milvus_example")


def create_sample_code_embeddings(count: int = 10) -> List[Dict[str, Any]]:
    """
    Create sample code embeddings for testing.
    
    Args:
        count: Number of embeddings to create
        
    Returns:
        List of dictionaries with vector and metadata
    """
    # Sample code entity types and languages
    entity_types = ["function", "class", "method", "module"]
    languages = ["python", "javascript", "java", "go", "rust"]
    
    # Generate sample embeddings
    embeddings = []
    for i in range(count):
        # Create random embedding vector (dimension 64 for testing)
        vector = np.random.rand(64).astype(np.float32)
        
        # Create sample metadata
        entity_type = entity_types[i % len(entity_types)]
        language = languages[i % len(languages)]
        
        metadata = format_code_metadata(
            file_path=f"/src/sample_{i}.{language}",
            language=language,
            entity_type=entity_type,
            entity_id=f"sample_entity_{i}",
            start_line=i * 10,
            end_line=i * 10 + 9,
            chunk_id=f"chunk_{i}",
            repository="sample_repo",
            branch="main",
            commit_id="abc123"
        )
        
        embeddings.append({
            "vector": vector,
            "metadata": metadata
        })
    
    return embeddings


def run_example():
    """Run the Milvus vector store example."""
    logger.info("Starting Milvus vector store example")
    
    # Configuration for Milvus (using test dimensions)
    config = {
        "type": "milvus",
        "milvus": {
            "host": "localhost",
            "port": 19530,
            "log_level": "INFO"
        }
    }
    
    try:
        # Create vector store instance
        logger.info("Creating vector store instance")
        vector_store = VectorStoreFactory.create_vector_store(config)
        
        # Connect to Milvus
        logger.info("Connecting to Milvus")
        if not vector_store.connect():
            logger.error("Failed to connect to Milvus. Make sure Milvus is running.")
            return
        
        # Check health
        health_info = vector_store.health_check()
        logger.info(f"Milvus health: {health_info['status']}")
        
        # Create test collection
        collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
        dimension = 64  # Small dimension for testing
        
        # Metadata schema
        metadata_schema = {
            "file_path": "string",
            "language": "string",
            "entity_type": "string",
            "entity_id": "string",
            "start_line": "int",
            "end_line": "int",
            "chunk_id": "string",
            "repository": "string"
        }
        
        logger.info(f"Creating collection: {collection_name}")
        success = vector_store.create_collection(
            name=collection_name,
            dimension=dimension,
            metadata_schema=metadata_schema
        )
        
        if not success:
            logger.error("Failed to create collection")
            return
        
        # List collections
        collections = vector_store.list_collections()
        logger.info(f"Available collections: {collections}")
        
        # Generate sample data
        sample_count = 20
        logger.info(f"Generating {sample_count} sample embeddings")
        embeddings = create_sample_code_embeddings(sample_count)
        
        # Insert vectors
        vectors = [item["vector"] for item in embeddings]
        metadata = [item["metadata"] for item in embeddings]
        
        logger.info("Inserting vectors")
        ids = vector_store.insert(
            collection=collection_name,
            vectors=vectors,
            metadata=metadata
        )
        
        if not ids:
            logger.error("Failed to insert vectors")
            return
            
        logger.info(f"Inserted {len(ids)} vectors")
        
        # Get collection stats
        stats = vector_store.collection_stats(collection_name)
        logger.info(f"Collection stats: {stats}")
        
        # Count vectors
        count = vector_store.count(collection_name)
        logger.info(f"Vector count: {count}")
        
        # Get some vectors by ID
        sample_ids = ids[:3]
        logger.info(f"Getting vectors by ID: {sample_ids}")
        retrieved = vector_store.get(collection_name, sample_ids)
        logger.info(f"Retrieved {len(retrieved)} vectors")
        
        # Search for similar vectors
        query_vector = vectors[0]
        logger.info("Searching for similar vectors")
        results = vector_store.search(
            collection=collection_name,
            query_vectors=[query_vector],
            top_k=5
        )
        
        logger.info(f"Found {len(results)} results")
        for i, result in enumerate(results):
            logger.info(f"  Result {i}: ID={result.id}, Score={result.score:.4f}")
            logger.info(f"    Entity: {result.metadata.get('entity_type')} - {result.metadata.get('entity_id')}")
            logger.info(f"    File: {result.metadata.get('file_path')}")
        
        # Search with filters
        logger.info("Searching with filters")
        python_filter = {"language": "python"}
        
        filtered_results = vector_store.search(
            collection=collection_name,
            query_vectors=[query_vector],
            top_k=5,
            filters=python_filter
        )
        
        logger.info(f"Found {len(filtered_results)} Python results")
        
        # Complex filter using FilterBuilder
        complex_filter = FilterBuilder.and_filter([
            FilterBuilder.exact_match("language", "python"),
            FilterBuilder.or_filter([
                FilterBuilder.exact_match("entity_type", "function"),
                FilterBuilder.exact_match("entity_type", "method")
            ])
        ])
        
        logger.info("Searching with complex filter")
        complex_results = vector_store.search(
            collection=collection_name,
            query_vectors=[query_vector],
            top_k=5,
            filters=complex_filter
        )
        
        logger.info(f"Found {len(complex_results)} results with complex filter")
        
        # Delete some vectors
        delete_ids = ids[:5]
        logger.info(f"Deleting {len(delete_ids)} vectors")
        deleted_count = vector_store.delete(collection_name, delete_ids)
        logger.info(f"Deleted {deleted_count} vectors")
        
        # Verify count after deletion
        new_count = vector_store.count(collection_name)
        logger.info(f"Vector count after deletion: {new_count}")
        
        # Delete by filter
        logger.info("Deleting vectors by filter")
        filter_delete_count = vector_store.delete(
            collection=collection_name,
            filters={"language": "java"}
        )
        logger.info(f"Deleted {filter_delete_count} Java vectors")
        
        # Clean up
        logger.info(f"Dropping collection {collection_name}")
        vector_store.drop_collection(collection_name)
        
        # Disconnect
        logger.info("Disconnecting from Milvus")
        vector_store.disconnect()
        
        logger.info("Example completed successfully")
        
    except Exception as e:
        logger.error(f"Error in example: {e}", exc_info=True)


if __name__ == "__main__":
    run_example()