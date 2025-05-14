"""
Pytest configuration for Code Indexer tests.

This module contains shared fixtures and configuration for tests.
"""

import os
import sys
import pytest
import numpy as np
import uuid
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List, Optional, Union

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Code Indexer components
from code_indexer.tools.vector_store_interface import VectorStoreInterface, SearchResult

# Conditionally import Milvus-related modules
try:
    from pymilvus import Collection, DataType, FieldSchema, CollectionSchema
    HAS_MILVUS = True
except ImportError:
    HAS_MILVUS = False


@pytest.fixture
def sample_code_chunk():
    """Sample code chunk for testing."""
    return """
def calculate_total(items):
    \"\"\"
    Calculate the total price of items.
    
    Args:
        items: List of items with 'price' attribute
        
    Returns:
        Total price
    \"\"\"
    return sum(item.price for item in items)
"""


@pytest.fixture
def sample_embedding():
    """Sample embedding vector for testing."""
    # Generate a deterministic random vector for tests
    np.random.seed(42)
    return np.random.rand(64).astype(np.float32)


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return {
        "file_path": "/src/sample.py",
        "language": "python",
        "entity_type": "function",
        "entity_id": "calculate_total",
        "start_line": 1,
        "end_line": 12,
        "chunk_id": "chunk_1",
        "repository": "sample_repo",
        "branch": "main",
        "commit_id": "abc123"
    }


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    mock = MagicMock(spec=VectorStoreInterface)
    
    # Set up the search method to return sample results
    def mock_search(*args, **kwargs):
        return [
            SearchResult(
                id="result1",
                score=0.95,
                metadata={
                    "file_path": "/src/sample.py",
                    "entity_type": "function",
                    "entity_id": "calculate_total"
                }
            ),
            SearchResult(
                id="result2",
                score=0.85,
                metadata={
                    "file_path": "/src/other.py",
                    "entity_type": "class",
                    "entity_id": "Calculator"
                }
            )
        ]
    
    mock.search.side_effect = mock_search
    return mock


@pytest.fixture
def mock_agent_context():
    """Mock agent context for testing."""
    mock = MagicMock()
    
    # Set up the get_tool method to return tool mocks
    def get_mock_tool(tool_name):
        tool_mock = MagicMock()
        mock_response = MagicMock()
        mock_response.status.is_success.return_value = True
        mock_response.tool = tool_mock
        return mock_response
    
    mock.get_tool.side_effect = get_mock_tool
    return mock


@pytest.fixture
def mock_neo4j_tool():
    """Mock Neo4j tool for testing."""
    mock = MagicMock()
    
    # Set up the execute_query method to return sample results
    def mock_execute_query(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status.is_success.return_value = True
        mock_response.data = {
            "results": [
                {
                    "func": {
                        "name": "calculate_total",
                        "parameters": ["items"],
                        "returnType": "float"
                    },
                    "filePath": "/src/sample.py",
                    "startLine": 1,
                    "endLine": 12,
                    "language": "python"
                }
            ]
        }
        return mock_response
    
    mock.execute_query.side_effect = mock_execute_query
    return mock


@pytest.fixture
def mock_embedding_tool():
    """Mock embedding tool for testing."""
    mock = MagicMock()
    
    # Set up the generate_embedding method to return sample embeddings
    def mock_generate_embedding(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status.is_success.return_value = True
        
        # Generate deterministic embedding
        np.random.seed(42)
        mock_response.data = {
            "embedding": np.random.rand(64).tolist(),
            "model": "test-model"
        }
        return mock_response
    
    mock.generate_embedding.side_effect = mock_generate_embedding
    return mock


@pytest.fixture
def fake_milvus_server(monkeypatch):
    """
    Mock Milvus server for integration tests.
    
    This fixture mocks the Milvus server connection and provides in-memory storage
    for collections and vectors during tests.
    """
    if not HAS_MILVUS:
        pytest.skip("Milvus dependencies not installed, skipping")
    
    # Create an in-memory database to simulate Milvus collections
    mock_db = {
        "collections": {},
        "indexes": {},
        "is_connected": False
    }
    
    # Mock Collection class
    class MockCollection:
        def __init__(self, name, schema=None):
            self.name = name
            self.schema = schema
            self.vectors = {}  # Store vectors using IDs as keys
            self.is_loaded = True
            self.num_entities = 0
            
            # Create collection if not exists
            if name not in mock_db["collections"]:
                mock_db["collections"][name] = self
            else:
                # Use existing collection data if already created
                existing = mock_db["collections"][name]
                self.vectors = existing.vectors
                self.num_entities = existing.num_entities
                self.schema = existing.schema or schema
        
        def insert(self, entities):
            count = len(entities["id"])
            for i in range(count):
                # Extract all fields for this entity
                entity = {"id": entities["id"][i], "vector": entities["vector"][i]}
                
                # Add metadata fields
                for field_name in entities:
                    if field_name not in ["id", "vector"]:
                        entity[field_name] = entities[field_name][i]
                
                # Store entity
                self.vectors[entity["id"]] = entity
            
            self.num_entities = len(self.vectors)
            return MagicMock()
        
        def search(self, data, anns_field, param, limit, expr=None, output_fields=None):
            results = []
            
            for query_vector in data:
                # For simplicity in testing, return predefined results
                # In real implementation, you'd compute vector similarity
                batch_results = []
                
                # Filter vectors based on expression if provided
                filtered_vectors = self._filter_vectors(expr)
                
                # Sort by arbitrary criteria for tests (in real usage would be by similarity)
                sorted_vectors = list(filtered_vectors.values())[:limit]
                
                for i, vector in enumerate(sorted_vectors):
                    # Mock hit with distance score and entity data
                    hit = MagicMock()
                    hit.id = vector["id"]
                    hit.distance = 0.9 - (i * 0.05)  # Decreasing score
                    
                    # Create entity with requested fields
                    entity = {}
                    if output_fields:
                        for field in output_fields:
                            if field in vector:
                                entity[field] = vector[field]
                    else:
                        entity = {k: v for k, v in vector.items() if k != "vector"}
                    
                    hit.entity = entity
                    batch_results.append(hit)
                
                results.append(batch_results)
            
            return results
        
        def query(self, expr, output_fields=None):
            filtered_vectors = self._filter_vectors(expr)
            
            # Handle special case for count
            if output_fields and "count(*)" in output_fields:
                return [{"count(*)": len(filtered_vectors)}]
            
            results = []
            for vector_id, vector in filtered_vectors.items():
                if output_fields and output_fields != ["*"]:
                    result = {field: vector.get(field) for field in output_fields if field in vector}
                else:
                    result = vector.copy()
                
                results.append(result)
            
            return results
        
        def create_index(self, field_name, index_type=None, metric_type=None, params=None):
            # Store index information
            if self.name not in mock_db["indexes"]:
                mock_db["indexes"][self.name] = {}
            
            mock_db["indexes"][self.name][field_name] = {
                "index_type": index_type,
                "metric_type": metric_type,
                "params": params
            }
        
        def index(self):
            # Return mock index info for primary search field ("vector")
            mock_index = MagicMock()
            if self.name in mock_db["indexes"] and "vector" in mock_db["indexes"][self.name]:
                mock_index.params = mock_db["indexes"][self.name]["vector"]
            else:
                mock_index.params = {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 8, "efConstruction": 64}}
            return mock_index
        
        def flush(self):
            # No-op in mock implementation
            pass
        
        def load(self):
            self.is_loaded = True
        
        def release(self):
            self.is_loaded = False
        
        def delete(self, expr):
            before_count = self.num_entities
            filtered_vectors = self._filter_vectors(expr)
            
            # Remove the filtered vectors
            for vector_id in filtered_vectors:
                if vector_id in self.vectors:
                    del self.vectors[vector_id]
            
            self.num_entities = len(self.vectors)
            
            # Return mock result with delete count
            result = MagicMock()
            result.delete_count = before_count - self.num_entities
            return result
        
        def _filter_vectors(self, expr):
            # Simple filtering for testing
            # In a real implementation, you'd parse and evaluate the expression
            if not expr:
                return self.vectors
            
            # Very basic expressions support for testing
            if "id in" in expr:
                # Extract IDs from expression like 'id in ["id1", "id2"]'
                import re
                id_match = re.search(r'id in \[(.*?)\]', expr)
                if id_match:
                    ids_str = id_match.group(1)
                    ids = [id.strip(' "\'') for id in ids_str.split(',')]
                    return {vector_id: vector for vector_id, vector in self.vectors.items() if vector_id in ids}
            
            # For other expressions, just return all vectors for test simplicity
            return self.vectors
    
    # Mock connections module
    class MockConnections:
        @staticmethod
        def connect(alias=None, host=None, port=None, user=None, password=None, secure=None, **kwargs):
            mock_db["is_connected"] = True
        
        @staticmethod
        def disconnect(alias=None):
            mock_db["is_connected"] = False
    
    # Mock utility module
    class MockUtility:
        @staticmethod
        def has_collection(collection_name):
            return collection_name in mock_db["collections"]
        
        @staticmethod
        def drop_collection(collection_name):
            if collection_name in mock_db["collections"]:
                del mock_db["collections"][collection_name]
                if collection_name in mock_db["indexes"]:
                    del mock_db["indexes"][collection_name]
        
        @staticmethod
        def list_collections():
            return list(mock_db["collections"].keys())
    
    # Apply patches
    with patch("pymilvus.connections", MockConnections()), \
         patch("pymilvus.Collection", MockCollection), \
         patch("pymilvus.utility", MockUtility()):
        yield mock_db