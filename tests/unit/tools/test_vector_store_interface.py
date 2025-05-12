"""
Tests for the VectorStoreInterface and related classes.
"""

import pytest
import numpy as np
from typing import Dict, Any, List

from code_indexer.tools.vector_store_interface import SearchResult


def test_search_result_init():
    """Test SearchResult initialization."""
    # Test with minimal parameters
    result = SearchResult(id="test1", score=0.95)
    assert result.id == "test1"
    assert result.score == 0.95
    assert result.metadata == {}
    assert result.vector is None
    
    # Test with full parameters
    vector = np.array([0.1, 0.2, 0.3])
    metadata = {"file": "test.py", "language": "python"}
    result = SearchResult(id="test2", score=0.85, metadata=metadata, vector=vector)
    assert result.id == "test2"
    assert result.score == 0.85
    assert result.metadata == metadata
    assert np.array_equal(result.vector, vector)


def test_search_result_to_dict():
    """Test SearchResult.to_dict method."""
    # Test with minimal parameters
    result = SearchResult(id="test1", score=0.95)
    result_dict = result.to_dict()
    assert result_dict["id"] == "test1"
    assert result_dict["score"] == 0.95
    assert result_dict["metadata"] == {}
    assert "vector" not in result_dict
    
    # Test with numpy vector
    vector = np.array([0.1, 0.2, 0.3])
    result = SearchResult(id="test2", score=0.85, vector=vector)
    result_dict = result.to_dict()
    assert "vector" in result_dict
    assert result_dict["vector"] == [0.1, 0.2, 0.3]
    
    # Test with list vector
    list_vector = [0.1, 0.2, 0.3]
    result = SearchResult(id="test3", score=0.85, vector=list_vector)
    result_dict = result.to_dict()
    assert "vector" in result_dict
    assert result_dict["vector"] == list_vector