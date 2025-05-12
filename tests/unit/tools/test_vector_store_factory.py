"""
Tests for the VectorStoreFactory.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.tools.vector_store_factory import VectorStoreFactory
from code_indexer.tools.vector_store_interface import VectorStoreInterface


# Mock the vector store implementations
class MockMilvusVectorStore(VectorStoreInterface):
    def __init__(self, config):
        self.config = config
    
    def connect(self):
        return True
    
    def disconnect(self):
        return True
    
    def create_collection(self, name, dimension, metadata_schema=None, distance_metric="cosine"):
        return True
    
    def collection_exists(self, name):
        return True
    
    def drop_collection(self, name):
        return True
    
    def list_collections(self):
        return ["collection1", "collection2"]
    
    def collection_stats(self, name):
        return {"name": name, "row_count": 100}
    
    def insert(self, collection, vectors, metadata=None, ids=None):
        return ["id1", "id2"]
    
    def search(self, collection, query_vectors, top_k=10, filters=None, output_fields=None):
        return []
    
    def get(self, collection, ids):
        return []
    
    def delete(self, collection, ids=None, filters=None):
        return 0
    
    def count(self, collection, filters=None):
        return 0
    
    def health_check(self):
        return {"status": "healthy"}


class MockQdrantVectorStore(VectorStoreInterface):
    def __init__(self, config):
        self.config = config
    
    def connect(self):
        return True
    
    def disconnect(self):
        return True
    
    def create_collection(self, name, dimension, metadata_schema=None, distance_metric="cosine"):
        return True
    
    def collection_exists(self, name):
        return True
    
    def drop_collection(self, name):
        return True
    
    def list_collections(self):
        return ["collection1", "collection2"]
    
    def collection_stats(self, name):
        return {"name": name, "row_count": 100}
    
    def insert(self, collection, vectors, metadata=None, ids=None):
        return ["id1", "id2"]
    
    def search(self, collection, query_vectors, top_k=10, filters=None, output_fields=None):
        return []
    
    def get(self, collection, ids):
        return []
    
    def delete(self, collection, ids=None, filters=None):
        return 0
    
    def count(self, collection, filters=None):
        return 0
    
    def health_check(self):
        return {"status": "healthy"}


@pytest.fixture
def mock_vector_stores():
    """Mock vector store implementations."""
    with patch('code_indexer.tools.vector_store_factory.MilvusVectorStore', MockMilvusVectorStore), \
         patch('code_indexer.tools.vector_store_factory.QdrantVectorStore', MockQdrantVectorStore), \
         patch('code_indexer.tools.vector_store_factory.HAS_MILVUS', True), \
         patch('code_indexer.tools.vector_store_factory.HAS_QDRANT', True):
        yield


def test_create_vector_store_milvus(mock_vector_stores):
    """Test creating a Milvus vector store."""
    config = {
        "type": "milvus",
        "milvus": {
            "host": "localhost",
            "port": 19530
        }
    }
    
    store = VectorStoreFactory.create_vector_store(config)
    
    assert isinstance(store, MockMilvusVectorStore)
    assert store.config == config["milvus"]


def test_create_vector_store_qdrant(mock_vector_stores):
    """Test creating a Qdrant vector store."""
    config = {
        "type": "qdrant",
        "qdrant": {
            "url": "http://localhost:6333"
        }
    }
    
    store = VectorStoreFactory.create_vector_store(config)
    
    assert isinstance(store, MockQdrantVectorStore)
    assert store.config == config["qdrant"]


def test_create_vector_store_unsupported(mock_vector_stores):
    """Test creating an unsupported vector store type."""
    config = {
        "type": "unsupported"
    }
    
    with pytest.raises(ValueError):
        VectorStoreFactory.create_vector_store(config)


def test_create_vector_store_missing_dependency():
    """Test creating a vector store with missing dependency."""
    with patch('code_indexer.tools.vector_store_factory.HAS_MILVUS', False):
        config = {
            "type": "milvus",
            "milvus": {
                "host": "localhost",
                "port": 19530
            }
        }
        
        with pytest.raises(ImportError):
            VectorStoreFactory.create_vector_store(config)


def test_available_stores():
    """Test getting available vector stores."""
    with patch('code_indexer.tools.vector_store_factory.HAS_MILVUS', True), \
         patch('code_indexer.tools.vector_store_factory.HAS_QDRANT', False):
        
        available = VectorStoreFactory.available_stores()
        
        assert available["milvus"] is True
        assert available["qdrant"] is False