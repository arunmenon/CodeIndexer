"""
Tests for the SearchOrchestratorAgent.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.agents.search_orchestrator_agent import SearchOrchestratorAgent

from google.adk.tools.google_api_tool import AgentContext, HandlerResponse
from google.adk.tools.google_api_tool import ToolResponse


@pytest.fixture
def mock_query_agent():
    """Create a mock query agent."""
    mock = MagicMock()
    
    # Configure run method
    def mock_run(params):
        mock_response = MagicMock(spec=ToolResponse)
        mock_response.status.is_success.return_value = True
        mock_response.data = {
            "search_spec": {
                "original_query": params.get("query", ""),
                "search_type": params.get("search_type", "hybrid"),
                "embeddings": {
                    "primary": [0.1, 0.2, 0.3],
                    "expanded": []
                },
                "analyzed_query": {
                    "intents": ["explanation"],
                    "entities": {}
                },
                "filters": params.get("filters", {})
            }
        }
        return mock_response
    
    mock.run.side_effect = mock_run
    
    return mock


@pytest.fixture
def mock_vector_search_agent():
    """Create a mock vector search agent."""
    mock = MagicMock()
    
    # Configure run method
    def mock_run(params):
        mock_response = MagicMock(spec=ToolResponse)
        mock_response.status.is_success.return_value = True
        mock_response.data = {
            "results": [
                {
                    "id": "result1",
                    "score": 0.95,
                    "file_path": "/src/auth.py",
                    "language": "python",
                    "entity_type": "function",
                    "entity_id": "authenticate_user",
                    "start_line": 10,
                    "end_line": 20,
                    "code_content": "def authenticate_user(username, password):\n    # Authentication logic\n    return True"
                }
            ],
            "total_count": 1,
            "collection": params.get("collection", "code_embeddings")
        }
        return mock_response
    
    mock.run.side_effect = mock_run
    
    return mock


@pytest.fixture
def mock_graph_search_agent():
    """Create a mock graph search agent."""
    mock = MagicMock()
    
    # Configure run method
    def mock_run(params):
        mock_response = MagicMock(spec=ToolResponse)
        mock_response.status.is_success.return_value = True
        mock_response.data = {
            "results": [
                {
                    "entity_type": "function",
                    "entity_id": "authenticate_user",
                    "file_path": "/src/auth.py",
                    "start_line": 10,
                    "end_line": 20,
                    "language": "python",
                    "search_type": "definition",
                    "parameters": ["username", "password"],
                    "return_type": "boolean"
                }
            ],
            "total_count": 1,
            "query_type": "definition"
        }
        return mock_response
    
    mock.run.side_effect = mock_run
    
    return mock


@pytest.fixture
def mock_answer_composer_agent():
    """Create a mock answer composer agent."""
    mock = MagicMock()
    
    # Configure run method
    def mock_run(params):
        mock_response = MagicMock(spec=ToolResponse)
        mock_response.status.is_success.return_value = True
        mock_response.data = {
            "answer": "Authentication works by validating user credentials against a database.",
            "code_snippets": [
                {
                    "entity_id": "authenticate_user",
                    "entity_type": "function",
                    "file_path": "/src/auth.py",
                    "language": "python",
                    "code": "def authenticate_user(username, password):\n    # Authentication logic\n    return True"
                }
            ],
            "query": params.get("original_query", ""),
            "total_results": 2
        }
        return mock_response
    
    mock.run.side_effect = mock_run
    
    return mock


@pytest.fixture
def mock_agent_context(mock_query_agent, mock_vector_search_agent, 
                     mock_graph_search_agent, mock_answer_composer_agent):
    """Mock agent context for testing."""
    mock = MagicMock(spec=AgentContext)
    
    # Configure the get_tool method to return the appropriate mock agent
    def get_mock_tool(tool_name):
        mock_tool_response = MagicMock()
        mock_tool_response.status.is_success.return_value = True
        
        if tool_name == "query_agent":
            mock_tool_response.tool = mock_query_agent
        elif tool_name == "vector_search_agent":
            mock_tool_response.tool = mock_vector_search_agent
        elif tool_name == "graph_search_agent":
            mock_tool_response.tool = mock_graph_search_agent
        elif tool_name == "answer_composer_agent":
            mock_tool_response.tool = mock_answer_composer_agent
        
        return mock_tool_response
    
    mock.get_tool.side_effect = get_mock_tool
    
    return mock


@pytest.fixture
def search_orchestrator_agent(mock_agent_context):
    """Create a SearchOrchestratorAgent instance for testing."""
    config = {
        "search_types": ["hybrid", "vector", "graph"],
        "enable_parallel": True,
        "vector_store_collection": "code_embeddings"
    }
    
    agent = SearchOrchestratorAgent(config)
    agent.init(mock_agent_context)
    
    return agent


def test_init(mock_agent_context):
    """Test SearchOrchestratorAgent initialization."""
    config = {
        "search_types": ["vector"],
        "enable_parallel": False,
        "vector_store_collection": "test_collection"
    }
    
    agent = SearchOrchestratorAgent(config)
    agent.init(mock_agent_context)
    
    assert agent.config == config
    assert agent.search_types == ["vector"]
    assert agent.enable_parallel is False
    assert agent.vector_store_collection == "test_collection"
    assert agent.query_agent is not None
    assert agent.vector_search_agent is not None
    assert agent.graph_search_agent is not None
    assert agent.answer_composer_agent is not None
    assert mock_agent_context.get_tool.call_count == 4


def test_run_with_empty_query(search_orchestrator_agent):
    """Test run method with empty query."""
    response = search_orchestrator_agent.run({})
    
    assert isinstance(response, HandlerResponse)
    assert not response.status.is_success()
    assert "No query provided" in response.status.message


def test_run_with_query_agent_failure(search_orchestrator_agent, mock_query_agent):
    """Test run method with query agent failure."""
    # Configure query agent to fail
    mock_response = MagicMock(spec=ToolResponse)
    mock_response.status.is_success.return_value = False
    mock_response.status.message = "Query processing failed"
    mock_query_agent.run.return_value = mock_response
    
    response = search_orchestrator_agent.run({
        "query": "How does authentication work?"
    })
    
    assert isinstance(response, HandlerResponse)
    assert not response.status.is_success()
    assert "Query processing failed" in response.status.message


def test_run_hybrid_search(search_orchestrator_agent, mock_query_agent, 
                          mock_vector_search_agent, mock_graph_search_agent,
                          mock_answer_composer_agent):
    """Test run method with hybrid search."""
    response = search_orchestrator_agent.run({
        "query": "How does authentication work?",
        "search_type": "hybrid",
        "max_results": 5,
        "filters": {"language": "python"}
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    
    # Check that all expected fields are in the response
    assert "answer" in response.data
    assert "code_snippets" in response.data
    assert "query" in response.data
    assert "search_spec" in response.data
    assert "vector_results" in response.data
    assert "graph_results" in response.data
    assert "total_results" in response.data
    
    # Check that agents were called with the right parameters
    mock_query_agent.run.assert_called_once()
    query_params = mock_query_agent.run.call_args[0][0]
    assert query_params["query"] == "How does authentication work?"
    assert query_params["search_type"] == "hybrid"
    assert query_params["max_results"] == 5
    assert query_params["filters"] == {"language": "python"}
    
    mock_vector_search_agent.run.assert_called_once()
    vector_params = mock_vector_search_agent.run.call_args[0][0]
    assert "search_spec" in vector_params
    assert vector_params["collection"] == "code_embeddings"
    assert vector_params["max_results"] == 5
    
    mock_graph_search_agent.run.assert_called_once()
    graph_params = mock_graph_search_agent.run.call_args[0][0]
    assert "search_spec" in graph_params
    assert graph_params["max_results"] == 5
    
    mock_answer_composer_agent.run.assert_called_once()
    composer_params = mock_answer_composer_agent.run.call_args[0][0]
    assert "original_query" in composer_params
    assert "search_spec" in composer_params
    assert "vector_results" in composer_params
    assert "graph_results" in composer_params


def test_run_vector_search_only(search_orchestrator_agent, mock_query_agent, 
                               mock_vector_search_agent, mock_graph_search_agent,
                               mock_answer_composer_agent):
    """Test run method with vector search only."""
    response = search_orchestrator_agent.run({
        "query": "How does authentication work?",
        "search_type": "vector",
        "max_results": 5
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    
    # Check that vector search was called but not graph search
    mock_vector_search_agent.run.assert_called_once()
    mock_graph_search_agent.run.assert_not_called()
    
    # Check that composer was called with empty graph results
    composer_params = mock_answer_composer_agent.run.call_args[0][0]
    assert "vector_results" in composer_params
    assert "graph_results" in composer_params
    assert len(composer_params["graph_results"]) == 0


def test_run_graph_search_only(search_orchestrator_agent, mock_query_agent, 
                              mock_vector_search_agent, mock_graph_search_agent,
                              mock_answer_composer_agent):
    """Test run method with graph search only."""
    response = search_orchestrator_agent.run({
        "query": "How does authentication work?",
        "search_type": "graph",
        "max_results": 5
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    
    # Check that graph search was called but not vector search
    mock_graph_search_agent.run.assert_called_once()
    mock_vector_search_agent.run.assert_not_called()
    
    # Check that composer was called with empty vector results
    composer_params = mock_answer_composer_agent.run.call_args[0][0]
    assert "vector_results" in composer_params
    assert "graph_results" in composer_params
    assert len(composer_params["vector_results"]) == 0


def test_perform_vector_search(search_orchestrator_agent, mock_vector_search_agent):
    """Test _perform_vector_search method."""
    search_spec = {
        "embeddings": {
            "primary": [0.1, 0.2, 0.3]
        },
        "filters": {"language": "python"}
    }
    
    results = search_orchestrator_agent._perform_vector_search(
        search_spec=search_spec,
        max_results=5
    )
    
    assert len(results) > 0
    assert isinstance(results[0], dict)
    assert "id" in results[0]
    assert "score" in results[0]
    assert "file_path" in results[0]
    
    # Check that vector search agent was called with the right parameters
    mock_vector_search_agent.run.assert_called_once()
    params = mock_vector_search_agent.run.call_args[0][0]
    assert params["search_spec"] == search_spec
    assert params["collection"] == search_orchestrator_agent.vector_store_collection
    assert params["max_results"] == 5


def test_perform_graph_search(search_orchestrator_agent, mock_graph_search_agent):
    """Test _perform_graph_search method."""
    search_spec = {
        "analyzed_query": {
            "intents": ["definition"],
            "entities": {
                "functions": ["authenticate_user"]
            }
        }
    }
    
    results = search_orchestrator_agent._perform_graph_search(
        search_spec=search_spec,
        max_results=5
    )
    
    assert len(results) > 0
    assert isinstance(results[0], dict)
    assert "entity_type" in results[0]
    assert "entity_id" in results[0]
    assert "file_path" in results[0]
    
    # Check that graph search agent was called with the right parameters
    mock_graph_search_agent.run.assert_called_once()
    params = mock_graph_search_agent.run.call_args[0][0]
    assert params["search_spec"] == search_spec
    assert params["max_results"] == 5


def test_perform_parallel_search(search_orchestrator_agent):
    """Test _perform_parallel_search method."""
    search_spec = {
        "embeddings": {
            "primary": [0.1, 0.2, 0.3]
        },
        "analyzed_query": {
            "intents": ["definition"],
            "entities": {
                "functions": ["authenticate_user"]
            }
        },
        "filters": {"language": "python"}
    }
    
    # Patch the sequential search methods to track calls
    with patch.object(search_orchestrator_agent, '_perform_vector_search') as mock_vector_search, \
         patch.object(search_orchestrator_agent, '_perform_graph_search') as mock_graph_search:
        
        # Configure the mocks to return sample results
        mock_vector_search.return_value = [{"id": "vec1", "source": "vector"}]
        mock_graph_search.return_value = [{"id": "graph1", "source": "graph"}]
        
        # Call the parallel search method
        vector_results, graph_results = search_orchestrator_agent._perform_parallel_search(
            search_spec=search_spec,
            max_results=5
        )
        
        # Check that both search methods were called
        mock_vector_search.assert_called_once_with(search_spec, 5)
        mock_graph_search.assert_called_once_with(search_spec, 5)
        
        # Check that results were returned correctly
        assert len(vector_results) == 1
        assert len(graph_results) == 1
        assert vector_results[0]["source"] == "vector"
        assert graph_results[0]["source"] == "graph"