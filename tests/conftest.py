"""
Pytest configuration for Code Indexer tests.

This module contains shared fixtures and configuration for tests.
"""

import os
import sys
import pytest
import numpy as np
from unittest.mock import MagicMock
from typing import Dict, Any, List

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Code Indexer components
from code_indexer.tools.vector_store_interface import VectorStoreInterface, SearchResult


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