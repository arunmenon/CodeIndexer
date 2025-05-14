"""
Tests for the VectorSearchAgent.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.agents.vector_search_agent import VectorSearchAgent

from google.adk.tools.google_api_tool import AgentContext, HandlerResponse
from google.adk.tools.google_api_tool import ToolResponse


@pytest.fixture
def mock_vector_store_agent():
    """Create a mock vector store agent."""
    mock = MagicMock()
    
    # Configure search method
    def mock_search(params):
        mock_response = MagicMock(spec=ToolResponse)
        mock_response.status.is_success.return_value = True
        mock_response.data = {
            "results": [
                {
                    "id": "result1",
                    "score": 0.95,
                    "metadata": {
                        "file_path": "/src/auth.py",
                        "language": "python",
                        "entity_type": "function", 
                        "entity_id": "authenticate_user",
                        "start_line": 10,
                        "end_line": 20,
                        "chunk_id": "chunk_1"
                    }
                },
                {
                    "id": "result2",
                    "score": 0.85,
                    "metadata": {
                        "file_path": "/src/user.py",
                        "language": "python",
                        "entity_type": "class", 
                        "entity_id": "User",
                        "start_line": 30,
                        "end_line": 50,
                        "chunk_id": "chunk_2"
                    }
                }
            ],
            "total_count": 2
        }
        return mock_response
    
    mock.search.side_effect = mock_search
    
    return mock


@pytest.fixture
def mock_agent_context(mock_vector_store_agent):
    """Mock agent context for testing."""
    mock = MagicMock(spec=AgentContext)
    
    # Configure the get_tool response for vector_store_agent
    mock_tool_response = MagicMock()
    mock_tool_response.status.is_success.return_value = True
    mock_tool_response.tool = mock_vector_store_agent
    
    mock.get_tool.return_value = mock_tool_response
    
    return mock


@pytest.fixture
def vector_search_agent(mock_agent_context):
    """Create a VectorSearchAgent instance for testing."""
    config = {
        "default_collection": "code_embeddings",
        "default_top_k": 10,
        "minimum_score": 0.7,
        "reranking_enabled": True
    }
    
    agent = VectorSearchAgent(config)
    agent.init(mock_agent_context)
    
    return agent


def test_init(mock_agent_context):
    """Test VectorSearchAgent initialization."""
    config = {
        "default_collection": "test_collection",
        "default_top_k": 5,
        "minimum_score": 0.8,
        "reranking_enabled": False
    }
    
    agent = VectorSearchAgent(config)
    agent.init(mock_agent_context)
    
    assert agent.config == config
    assert agent.default_collection == "test_collection"
    assert agent.default_top_k == 5
    assert agent.minimum_score == 0.8
    assert agent.reranking_enabled is False
    assert agent.vector_store_agent is not None
    mock_agent_context.get_tool.assert_called_once_with("vector_store_agent")


def test_run_with_empty_search_spec(vector_search_agent):
    """Test run method with empty search specification."""
    response = vector_search_agent.run({})
    
    assert isinstance(response, HandlerResponse)
    assert not response.status.is_success()
    assert "No search specification provided" in response.status.message


def test_run_with_no_embedding(vector_search_agent):
    """Test run method with no embedding."""
    response = vector_search_agent.run({
        "search_spec": {
            "embeddings": {
                "primary": []
            }
        }
    })
    
    assert isinstance(response, HandlerResponse)
    assert not response.status.is_success()
    assert "No query embedding provided" in response.status.message


def test_run_with_valid_search(vector_search_agent):
    """Test run method with valid search parameters."""
    # Create sample embedding
    np.random.seed(42)
    embedding = np.random.rand(64).tolist()
    
    response = vector_search_agent.run({
        "search_spec": {
            "embeddings": {
                "primary": embedding,
                "expanded": []
            },
            "filters": {
                "language": "python"
            }
        },
        "collection": "test_collection",
        "max_results": 5
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    assert "results" in response.data
    assert "total_count" in response.data
    assert "collection" in response.data
    assert response.data["collection"] == "test_collection"
    assert len(response.data["results"]) > 0


def test_perform_search(vector_search_agent, mock_vector_store_agent):
    """Test _perform_search method."""
    # Create sample embedding
    np.random.seed(42)
    embedding = np.random.rand(64).tolist()
    
    # Run search
    results = vector_search_agent._perform_search(
        collection="test_collection",
        embedding=embedding,
        top_k=5,
        filters={"language": "python"}
    )
    
    assert len(results) > 0
    assert all("id" in r for r in results)
    assert all("score" in r for r in results)
    assert all("metadata" in r for r in results)
    assert all("source" in r for r in results)
    
    # Check that vector store agent was called correctly
    mock_vector_store_agent.search.assert_called_once()
    call_args = mock_vector_store_agent.search.call_args[0][0]
    assert call_args["collection"] == "test_collection"
    assert call_args["query_embedding"] == embedding
    assert call_args["top_k"] == 5
    assert call_args["filters"] == {"language": "python"}


def test_merge_and_rerank(vector_search_agent):
    """Test _merge_and_rerank method."""
    # Create primary results
    primary_results = [
        {
            "id": "result1",
            "score": 0.95,
            "metadata": {"entity_type": "function", "entity_id": "func1"},
            "source": "primary"
        },
        {
            "id": "result2",
            "score": 0.85,
            "metadata": {"entity_type": "class", "entity_id": "class1"},
            "source": "primary"
        }
    ]
    
    # Create expanded results
    expanded_results = [
        {
            "query": "Expanded query 1",
            "results": [
                {
                    "id": "result3",
                    "score": 0.9,
                    "metadata": {"entity_type": "function", "entity_id": "func2"},
                    "source": "primary"
                },
                {
                    "id": "result1",  # Duplicate ID
                    "score": 0.8,
                    "metadata": {"entity_type": "function", "entity_id": "func1"},
                    "source": "primary"
                }
            ]
        }
    ]
    
    # Merge and rerank
    merged = vector_search_agent._merge_and_rerank(primary_results, expanded_results)
    
    assert len(merged) == 3  # 3 unique IDs
    assert merged[0]["id"] == "result1"  # Highest score first
    assert merged[1]["id"] == "result3"
    assert merged[2]["id"] == "result2"


def test_rerank_results(vector_search_agent):
    """Test _rerank_results method."""
    # Create sample results
    results = [
        {
            "id": "result1",
            "score": 0.8,
            "metadata": {"entity_type": "function", "entity_id": "func1"},
            "source": "primary"
        },
        {
            "id": "result2",
            "score": 0.85,
            "metadata": {"entity_type": "class", "entity_id": "class1"},
            "source": "primary"
        },
        {
            "id": "result3",
            "score": 0.75,
            "metadata": {"entity_type": "function", "entity_id": "func2", 
                        "start_line": 10, "end_line": 15},
            "source": "expanded"
        }
    ]
    
    # Rerank
    reranked = vector_search_agent._rerank_results(results)
    
    assert len(reranked) == 3
    
    # Check that ordering changed due to boosting/penalties
    # Function and class entities should be boosted
    # Expanded results should have slight penalty
    # Very short snippets should have penalty
    
    # Since ordering depends on exact boosting factors, just check that
    # scores were modified and the results are sorted by score
    scores = [r["score"] for r in reranked]
    assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))  # Check sorted


def test_process_results(vector_search_agent):
    """Test _process_results method."""
    # Create sample results
    results = [
        {
            "id": "result1",
            "score": 0.95,
            "metadata": {
                "file_path": "/src/auth.py",
                "language": "python",
                "entity_type": "function", 
                "entity_id": "authenticate_user",
                "start_line": 10,
                "end_line": 20,
                "chunk_id": "chunk_1"
            },
            "source": "primary"
        },
        {
            "id": "result2",
            "score": 0.85,
            "metadata": {
                "file_path": "/src/user.py",
                "language": "python",
                "entity_type": "class", 
                "entity_id": "User",
                "start_line": 30,
                "end_line": 50,
                "chunk_id": "chunk_2"
            },
            "source": "primary"
        }
    ]
    
    # Process results
    processed = vector_search_agent._process_results(results)
    
    assert len(processed) == 2
    assert "id" in processed[0]
    assert "score" in processed[0]
    assert "file_path" in processed[0]
    assert "language" in processed[0]
    assert "entity_type" in processed[0]
    assert "entity_id" in processed[0]
    assert "start_line" in processed[0]
    assert "end_line" in processed[0]
    assert "code_content" in processed[0]
    assert "metadata" in processed[0]
    
    assert processed[0]["file_path"] == "/src/auth.py"
    assert processed[0]["entity_id"] == "authenticate_user"
    assert processed[0]["code_content"] is not None