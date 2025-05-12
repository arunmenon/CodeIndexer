"""
Tests for vector store utilities.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, mock_open
from typing import Dict, Any, List

from code_indexer.utils.vector_store_utils import (
    FilterBuilder, load_vector_store_config, 
    get_code_metadata_schema, format_code_metadata
)


def test_filter_builder_exact_match():
    """Test FilterBuilder.exact_match method."""
    filter_expr = FilterBuilder.exact_match("language", "python")
    
    assert filter_expr["operator"] == "=="
    assert filter_expr["field"] == "language"
    assert filter_expr["value"] == "python"


def test_filter_builder_not_equal():
    """Test FilterBuilder.not_equal method."""
    filter_expr = FilterBuilder.not_equal("language", "python")
    
    assert filter_expr["operator"] == "!="
    assert filter_expr["field"] == "language"
    assert filter_expr["value"] == "python"


def test_filter_builder_in_list():
    """Test FilterBuilder.in_list method."""
    filter_expr = FilterBuilder.in_list("language", ["python", "javascript"])
    
    assert filter_expr["operator"] == "in"
    assert filter_expr["field"] == "language"
    assert filter_expr["value"] == ["python", "javascript"]


def test_filter_builder_range():
    """Test FilterBuilder.range method."""
    # Test with all parameters
    filter_expr = FilterBuilder.range("line_count", gt=10, gte=None, lt=50, lte=None)
    
    assert filter_expr["operator"] == "range"
    assert filter_expr["field"] == "line_count"
    assert "gt" in filter_expr["conditions"]
    assert filter_expr["conditions"]["gt"] == 10
    assert "lt" in filter_expr["conditions"]
    assert filter_expr["conditions"]["lt"] == 50
    assert "gte" not in filter_expr["conditions"]
    assert "lte" not in filter_expr["conditions"]
    
    # Test with only gte and lte
    filter_expr = FilterBuilder.range("line_count", gte=10, lte=50)
    
    assert "gte" in filter_expr["conditions"]
    assert filter_expr["conditions"]["gte"] == 10
    assert "lte" in filter_expr["conditions"]
    assert filter_expr["conditions"]["lte"] == 50
    assert "gt" not in filter_expr["conditions"]
    assert "lt" not in filter_expr["conditions"]


def test_filter_builder_and_filter():
    """Test FilterBuilder.and_filter method."""
    filter1 = FilterBuilder.exact_match("language", "python")
    filter2 = FilterBuilder.exact_match("entity_type", "function")
    
    and_filter = FilterBuilder.and_filter([filter1, filter2])
    
    assert and_filter["operator"] == "and"
    assert len(and_filter["conditions"]) == 2
    assert and_filter["conditions"][0] == filter1
    assert and_filter["conditions"][1] == filter2


def test_filter_builder_or_filter():
    """Test FilterBuilder.or_filter method."""
    filter1 = FilterBuilder.exact_match("language", "python")
    filter2 = FilterBuilder.exact_match("language", "javascript")
    
    or_filter = FilterBuilder.or_filter([filter1, filter2])
    
    assert or_filter["operator"] == "or"
    assert len(or_filter["conditions"]) == 2
    assert or_filter["conditions"][0] == filter1
    assert or_filter["conditions"][1] == filter2


def test_complex_filter_builder():
    """Test building a complex filter with FilterBuilder."""
    # Create a filter for Python functions or methods with line count between 10 and 100
    language_filter = FilterBuilder.exact_match("language", "python")
    
    entity_type_function = FilterBuilder.exact_match("entity_type", "function")
    entity_type_method = FilterBuilder.exact_match("entity_type", "method")
    entity_type_filter = FilterBuilder.or_filter([entity_type_function, entity_type_method])
    
    line_count_filter = FilterBuilder.range("line_count", gte=10, lte=100)
    
    complex_filter = FilterBuilder.and_filter([
        language_filter,
        entity_type_filter,
        line_count_filter
    ])
    
    assert complex_filter["operator"] == "and"
    assert len(complex_filter["conditions"]) == 3
    assert complex_filter["conditions"][0] == language_filter
    assert complex_filter["conditions"][1]["operator"] == "or"
    assert complex_filter["conditions"][2]["operator"] == "range"


def test_load_vector_store_config_with_path():
    """Test loading vector store config with explicit path."""
    mock_config = {
        "vector_store": {
            "type": "milvus",
            "milvus": {
                "host": "localhost",
                "port": 19530
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml') as temp_file:
        # Use patch to mock yaml.safe_load
        with patch('yaml.safe_load', return_value=mock_config):
            # Call the function with the temp file path
            config = load_vector_store_config(temp_file.name)
            
            assert config["type"] == "milvus"
            assert config["milvus"]["host"] == "localhost"
            assert config["milvus"]["port"] == 19530


def test_load_vector_store_config_default():
    """Test loading vector store config with default locations."""
    # Mock all file checks to return False
    with patch('os.path.exists', return_value=False):
        # Call the function with no arguments
        config = load_vector_store_config()
        
        # Should return default config
        assert config["type"] == "milvus"
        assert "milvus" in config
        assert "host" in config["milvus"]
        assert "port" in config["milvus"]


def test_get_code_metadata_schema():
    """Test getting code metadata schema."""
    schema = get_code_metadata_schema()
    
    assert "file_path" in schema
    assert schema["file_path"] == "string"
    assert "language" in schema
    assert schema["language"] == "string"
    assert "entity_type" in schema
    assert schema["entity_type"] == "string"
    assert "start_line" in schema
    assert schema["start_line"] == "int"


def test_format_code_metadata():
    """Test formatting code metadata."""
    # Test with required parameters
    metadata = format_code_metadata(
        file_path="/src/sample.py",
        language="python",
        entity_type="function",
        entity_id="sample_function",
        start_line=10,
        end_line=20,
        chunk_id="chunk_1"
    )
    
    assert metadata["file_path"] == "/src/sample.py"
    assert metadata["language"] == "python"
    assert metadata["entity_type"] == "function"
    assert metadata["entity_id"] == "sample_function"
    assert metadata["start_line"] == 10
    assert metadata["end_line"] == 20
    assert metadata["chunk_id"] == "chunk_1"
    assert "indexed_at" in metadata
    assert "repository" not in metadata
    assert "branch" not in metadata
    assert "commit_id" not in metadata
    
    # Test with optional parameters
    metadata = format_code_metadata(
        file_path="/src/sample.py",
        language="python",
        entity_type="function",
        entity_id="sample_function",
        start_line=10,
        end_line=20,
        chunk_id="chunk_1",
        repository="test_repo",
        branch="main",
        commit_id="abc123",
        complexity=5
    )
    
    assert metadata["repository"] == "test_repo"
    assert metadata["branch"] == "main"
    assert metadata["commit_id"] == "abc123"
    assert metadata["complexity"] == 5