"""
Tests for the MilvusVectorStore implementation.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

# Skip tests if pymilvus is not available
pymilvus_not_installed = False
try:
    import pymilvus
except ImportError:
    pymilvus_not_installed = True

# Only import MilvusVectorStore if pymilvus is available
if not pymilvus_not_installed:
    from code_indexer.tools.milvus_vector_store import MilvusVectorStore, HAS_MILVUS
else:
    # Create stub for testing without pymilvus
    HAS_MILVUS = False


# Skip all tests if pymilvus is not available
pytestmark = pytest.mark.skipif(
    pymilvus_not_installed or not HAS_MILVUS,
    reason="pymilvus is not installed"
)


@pytest.fixture
def mock_pymilvus():
    """Mock the pymilvus module for testing."""
    with patch('code_indexer.tools.milvus_vector_store.connections') as mock_connections, \
         patch('code_indexer.tools.milvus_vector_store.Collection') as mock_collection, \
         patch('code_indexer.tools.milvus_vector_store.utility') as mock_utility, \
         patch('code_indexer.tools.milvus_vector_store.CollectionSchema') as mock_schema, \
         patch('code_indexer.tools.milvus_vector_store.FieldSchema') as mock_field_schema, \
         patch('code_indexer.tools.milvus_vector_store.DataType') as mock_data_type:
        
        # Set up mocks for common operations
        mock_utility.has_collection.return_value = False
        mock_utility.list_collections.return_value = ["test_collection"]
        
        # Mock DataType enum values
        mock_data_type.VARCHAR = "VARCHAR"
        mock_data_type.FLOAT_VECTOR = "FLOAT_VECTOR"
        mock_data_type.INT64 = "INT64"
        mock_data_type.FLOAT = "FLOAT"
        mock_data_type.DOUBLE = "DOUBLE"
        mock_data_type.BOOLEAN = "BOOLEAN"
        
        # Return mock collection instance
        mock_col_instance = MagicMock()
        mock_collection.return_value = mock_col_instance
        
        # Set up collection methods
        mock_col_instance.insert.return_value = MagicMock()
        mock_col_instance.flush.return_value = None
        mock_col_instance.search.return_value = []
        mock_col_instance.query.return_value = []
        mock_col_instance.delete.return_value = MagicMock(delete_count=0)
        mock_col_instance.schema.fields = []
        mock_col_instance.num_entities = 0
        mock_col_instance.is_loaded = True
        
        # Set up index info
        mock_col_instance.index.return_value = MagicMock(params={"index_type": "HNSW"})
        
        yield {
            "connections": mock_connections,
            "collection": mock_collection,
            "utility": mock_utility,
            "schema": mock_schema,
            "field_schema": mock_field_schema,
            "data_type": mock_data_type,
            "collection_instance": mock_col_instance
        }


@pytest.fixture
def milvus_store(mock_pymilvus):
    """Create a MilvusVectorStore instance for testing."""
    config = {
        "host": "localhost",
        "port": 19530,
        "log_level": "DEBUG"
    }
    store = MilvusVectorStore(config)
    return store


def test_init(mock_pymilvus):
    """Test MilvusVectorStore initialization."""
    config = {
        "host": "localhost",
        "port": 19530,
        "connection_alias": "test_alias",
        "log_level": "INFO"
    }
    store = MilvusVectorStore(config)
    
    assert store.config == config
    assert store.connection_alias == "test_alias"
    assert store.connected is False
    assert store._collections == {}


def test_connect(milvus_store, mock_pymilvus):
    """Test connect method."""
    # Test successful connection
    result = milvus_store.connect()
    
    assert result is True
    assert milvus_store.connected is True
    mock_pymilvus["connections"].connect.assert_called_once()
    
    # Test connection failure
    mock_pymilvus["connections"].connect.side_effect = Exception("Connection failed")
    result = milvus_store.connect()
    
    assert result is False
    assert milvus_store.connected is False


def test_disconnect(milvus_store, mock_pymilvus):
    """Test disconnect method."""
    # Connect first
    milvus_store.connect()
    assert milvus_store.connected is True
    
    # Test successful disconnection
    result = milvus_store.disconnect()
    
    assert result is True
    assert milvus_store.connected is False
    assert milvus_store._collections == {}
    mock_pymilvus["connections"].disconnect.assert_called_once_with(milvus_store.connection_alias)
    
    # Test disconnection failure
    mock_pymilvus["connections"].disconnect.side_effect = Exception("Disconnection failed")
    result = milvus_store.disconnect()
    
    assert result is False


def test_create_collection(milvus_store, mock_pymilvus):
    """Test create_collection method."""
    # Test creating a new collection
    mock_pymilvus["utility"].has_collection.return_value = False
    
    result = milvus_store.create_collection(
        name="test_collection",
        dimension=128,
        metadata_schema={
            "file_path": "string",
            "language": "string"
        }
    )
    
    assert result is True
    mock_pymilvus["collection"].assert_called_once()
    mock_pymilvus["collection_instance"].create_index.assert_called()
    assert "test_collection" in milvus_store._collections
    
    # Test with existing collection
    mock_pymilvus["utility"].has_collection.return_value = True
    mock_pymilvus["collection"].reset_mock()
    
    result = milvus_store.create_collection(
        name="existing_collection",
        dimension=128
    )
    
    assert result is True
    mock_pymilvus["collection"].assert_not_called()


def test_collection_exists(milvus_store, mock_pymilvus):
    """Test collection_exists method."""
    # Test for existing collection
    mock_pymilvus["utility"].has_collection.return_value = True
    
    result = milvus_store.collection_exists("test_collection")
    assert result is True
    
    # Test for non-existing collection
    mock_pymilvus["utility"].has_collection.return_value = False
    
    result = milvus_store.collection_exists("nonexistent_collection")
    assert result is False
    
    # Test with exception
    mock_pymilvus["utility"].has_collection.side_effect = Exception("Error")
    
    result = milvus_store.collection_exists("error_collection")
    assert result is False


def test_drop_collection(milvus_store, mock_pymilvus):
    """Test drop_collection method."""
    # Add a collection to the cache
    milvus_store._collections["test_collection"] = MagicMock()
    
    # Test dropping an existing collection
    mock_pymilvus["utility"].has_collection.return_value = True
    
    result = milvus_store.drop_collection("test_collection")
    
    assert result is True
    mock_pymilvus["utility"].drop_collection.assert_called_once_with("test_collection")
    assert "test_collection" not in milvus_store._collections
    
    # Test dropping a non-existing collection
    mock_pymilvus["utility"].has_collection.return_value = False
    
    result = milvus_store.drop_collection("nonexistent_collection")
    
    assert result is False
    
    # Test with exception
    mock_pymilvus["utility"].has_collection.return_value = True
    mock_pymilvus["utility"].drop_collection.side_effect = Exception("Error")
    
    result = milvus_store.drop_collection("error_collection")
    
    assert result is False


def test_list_collections(milvus_store, mock_pymilvus):
    """Test list_collections method."""
    # Test successful listing
    mock_pymilvus["utility"].list_collections.return_value = ["collection1", "collection2"]
    
    result = milvus_store.list_collections()
    
    assert result == ["collection1", "collection2"]
    mock_pymilvus["utility"].list_collections.assert_called_once()
    
    # Test with exception
    mock_pymilvus["utility"].list_collections.side_effect = Exception("Error")
    
    result = milvus_store.list_collections()
    
    assert result == []


def test_insert(milvus_store, mock_pymilvus):
    """Test insert method."""
    # Set up a mock collection
    mock_collection = MagicMock()
    mock_collection.schema.fields = [
        MagicMock(name="id"),
        MagicMock(name="vector"),
        MagicMock(name="file_path", dtype=mock_pymilvus["data_type"].VARCHAR)
    ]
    milvus_store._get_collection = MagicMock(return_value=mock_collection)
    
    # Test inserting vectors
    vectors = [np.random.rand(128) for _ in range(3)]
    metadata = [
        {"file_path": "file1.py", "language": "python"},
        {"file_path": "file2.py", "language": "python"},
        {"file_path": "file3.py", "language": "python"}
    ]
    ids = ["id1", "id2", "id3"]
    
    result = milvus_store.insert(
        collection="test_collection",
        vectors=vectors,
        metadata=metadata,
        ids=ids
    )
    
    assert result == ids
    mock_collection.insert.assert_called_once()
    mock_collection.flush.assert_called_once()
    
    # Test with missing collection
    milvus_store._get_collection = MagicMock(return_value=None)
    
    result = milvus_store.insert(
        collection="nonexistent_collection",
        vectors=vectors,
        metadata=metadata
    )
    
    assert result == []


def test_search(milvus_store, mock_pymilvus):
    """Test search method."""
    # Set up mock collection and search results
    mock_collection = MagicMock()
    mock_collection.is_loaded = True
    mock_collection.index.return_value = MagicMock(params={"index_type": "HNSW"})
    
    # Create mock search results
    mock_hit1 = MagicMock()
    mock_hit1.id = "id1"
    mock_hit1.distance = 0.95
    mock_hit1.entity = {"id": "id1", "file_path": "file1.py", "language": "python"}
    
    mock_hit2 = MagicMock()
    mock_hit2.id = "id2"
    mock_hit2.distance = 0.85
    mock_hit2.entity = {"id": "id2", "file_path": "file2.py", "language": "python"}
    
    mock_collection.search.return_value = [[mock_hit1, mock_hit2]]
    milvus_store._get_collection = MagicMock(return_value=mock_collection)
    
    # Test searching
    query_vectors = [np.random.rand(128)]
    
    result = milvus_store.search(
        collection="test_collection",
        query_vectors=query_vectors,
        top_k=2,
        filters={"language": "python"}
    )
    
    assert len(result) == 2
    assert result[0].id == "id1"
    assert result[0].score == 0.95
    assert result[0].metadata["file_path"] == "file1.py"
    assert result[1].id == "id2"
    assert result[1].score == 0.85
    mock_collection.search.assert_called_once()
    
    # Test with missing collection
    milvus_store._get_collection = MagicMock(return_value=None)
    
    result = milvus_store.search(
        collection="nonexistent_collection",
        query_vectors=query_vectors
    )
    
    assert result == []


def test_delete(milvus_store, mock_pymilvus):
    """Test delete method."""
    # Set up mock collection and delete results
    mock_collection = MagicMock()
    mock_result = MagicMock()
    mock_result.delete_count = 3
    mock_collection.delete.return_value = mock_result
    milvus_store._get_collection = MagicMock(return_value=mock_collection)
    
    # Test deleting by IDs
    result = milvus_store.delete(
        collection="test_collection",
        ids=["id1", "id2", "id3"]
    )
    
    assert result == 3
    mock_collection.delete.assert_called_once()
    
    # Test deleting by filters
    mock_collection.delete.reset_mock()
    milvus_store._convert_filters = MagicMock(return_value="language == 'python'")
    
    result = milvus_store.delete(
        collection="test_collection",
        filters={"language": "python"}
    )
    
    assert result == 3
    mock_collection.delete.assert_called_once()
    
    # Test with missing collection
    milvus_store._get_collection = MagicMock(return_value=None)
    
    result = milvus_store.delete(
        collection="nonexistent_collection",
        ids=["id1"]
    )
    
    assert result == 0
    
    # Test with no criteria
    milvus_store._get_collection = MagicMock(return_value=mock_collection)
    
    with pytest.raises(ValueError):
        milvus_store.delete(
            collection="test_collection"
        )


def test_count(milvus_store, mock_pymilvus):
    """Test count method."""
    # Set up mock collection
    mock_collection = MagicMock()
    mock_collection.num_entities = 10
    milvus_store._get_collection = MagicMock(return_value=mock_collection)
    
    # Test counting all vectors
    result = milvus_store.count(
        collection="test_collection"
    )
    
    assert result == 10
    
    # Test with missing collection
    milvus_store._get_collection = MagicMock(return_value=None)
    
    result = milvus_store.count(
        collection="nonexistent_collection"
    )
    
    assert result == 0


def test_convert_filters(milvus_store):
    """Test _convert_filters method."""
    # Test flat filters
    filters = {
        "language": "python",
        "entity_type": "function"
    }
    
    result = milvus_store._convert_filters(filters)
    
    assert "language == \"python\"" in result
    assert "entity_type == \"function\"" in result
    assert "&&" in result
    
    # Test empty filters
    result = milvus_store._convert_filters({})
    
    assert result is None
    
    # Test filters with lists
    filters = {
        "language": ["python", "javascript"]
    }
    
    result = milvus_store._convert_filters(filters)
    
    assert "language in [\"python\", \"javascript\"]" in result
    
    # Test numeric filters
    filters = {
        "line_count": 100
    }
    
    result = milvus_store._convert_filters(filters)
    
    assert "line_count == 100" in result