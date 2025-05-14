"""
Tests for the AnswerComposerAgent.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.agents.answer_composer_agent import AnswerComposerAgent

from google.adk.tools.google_api_tool import AgentContext, HandlerResponse
from google.adk.tools.google_api_tool import ToolResponse


@pytest.fixture
def mock_embedding_tool():
    """Create a mock embedding tool."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_agent_context(mock_embedding_tool):
    """Mock agent context for testing."""
    mock = MagicMock(spec=AgentContext)
    
    # Configure the get_tool response for embedding_tool
    mock_tool_response = MagicMock()
    mock_tool_response.status.is_success.return_value = True
    mock_tool_response.tool = mock_embedding_tool
    
    mock.get_tool.return_value = mock_tool_response
    
    return mock


@pytest.fixture
def sample_vector_results():
    """Sample vector search results for testing."""
    return [
        {
            "id": "vec1",
            "score": 0.95,
            "file_path": "/src/auth.py",
            "language": "python",
            "entity_type": "function",
            "entity_id": "authenticate_user",
            "start_line": 10,
            "end_line": 20,
            "code_content": "def authenticate_user(username, password):\n    # Authentication logic\n    return True"
        },
        {
            "id": "vec2",
            "score": 0.85,
            "file_path": "/src/user.py",
            "language": "python",
            "entity_type": "class",
            "entity_id": "User",
            "start_line": 30,
            "end_line": 50,
            "code_content": "class User:\n    def __init__(self, username):\n        self.username = username"
        }
    ]


@pytest.fixture
def sample_graph_results():
    """Sample graph search results for testing."""
    return [
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
        },
        {
            "entity_type": "function",
            "entity_id": "authenticate_user",
            "file_path": "/src/login.py",
            "start_line": 30,
            "end_line": 40,
            "language": "python",
            "search_type": "usage",
            "caller_type": "function",
            "caller_name": "login"
        }
    ]


@pytest.fixture
def answer_composer_agent(mock_agent_context):
    """Create an AnswerComposerAgent instance for testing."""
    config = {
        "max_code_snippets": 3,
        "include_explanations": True,
        "llm_model": "test-model",
        "answer_style": "concise"
    }
    
    agent = AnswerComposerAgent(config)
    agent.init(mock_agent_context)
    
    return agent


def test_init(mock_agent_context):
    """Test AnswerComposerAgent initialization."""
    config = {
        "max_code_snippets": 2,
        "include_explanations": False,
        "llm_model": "gpt-4",
        "answer_style": "detailed"
    }
    
    agent = AnswerComposerAgent(config)
    agent.init(mock_agent_context)
    
    assert agent.config == config
    assert agent.max_code_snippets == 2
    assert agent.include_explanations is False
    assert agent.llm_model == "gpt-4"
    assert agent.answer_style == "detailed"
    assert agent.embedding_tool is not None
    mock_agent_context.get_tool.assert_called_once_with("embedding_tool")


def test_run_with_empty_query(answer_composer_agent):
    """Test run method with empty query."""
    response = answer_composer_agent.run({})
    
    assert isinstance(response, HandlerResponse)
    assert not response.status.is_success()
    assert "No query provided" in response.status.message


def test_run_with_no_results(answer_composer_agent):
    """Test run method with no search results."""
    response = answer_composer_agent.run({
        "original_query": "How does authentication work?",
        "search_spec": {
            "analyzed_query": {
                "intents": ["explanation"]
            }
        },
        "vector_results": [],
        "graph_results": []
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    assert "answer" in response.data
    assert "results" in response.data
    assert "query" in response.data
    assert "couldn't find any relevant information" in response.data["answer"].lower()
    assert response.data["results"] == []
    assert response.data["query"] == "How does authentication work?"


def test_run_with_results(answer_composer_agent, sample_vector_results, sample_graph_results):
    """Test run method with search results."""
    response = answer_composer_agent.run({
        "original_query": "How does authentication work?",
        "search_spec": {
            "analyzed_query": {
                "intents": ["explanation"]
            }
        },
        "vector_results": sample_vector_results,
        "graph_results": sample_graph_results
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    assert "answer" in response.data
    assert "code_snippets" in response.data
    assert "query" in response.data
    assert "total_results" in response.data
    assert response.data["query"] == "How does authentication work?"
    assert response.data["total_results"] > 0
    assert len(response.data["code_snippets"]) <= answer_composer_agent.max_code_snippets


def test_combine_results(answer_composer_agent, sample_vector_results, sample_graph_results):
    """Test _combine_results method."""
    combined = answer_composer_agent._combine_results(
        sample_vector_results, sample_graph_results)
    
    assert len(combined) > 0
    
    # Check for duplicates being merged
    duplicate_paths = [result for result in combined 
                       if result["file_path"] == "/src/auth.py" and 
                       result["entity_id"] == "authenticate_user"]
    
    assert len(duplicate_paths) == 1
    assert duplicate_paths[0]["source"] == "both"
    
    # Check that unique results are preserved
    unique_paths = [result for result in combined 
                    if result["file_path"] == "/src/user.py"]
    
    assert len(unique_paths) == 1
    
    # Check that results from different files are preserved
    login_paths = [result for result in combined 
                  if result["file_path"] == "/src/login.py"]
    
    assert len(login_paths) == 1


def test_rank_results(answer_composer_agent):
    """Test _rank_results method."""
    results = [
        {
            "id": "result1",
            "score": 0.8,
            "entity_type": "function",
            "source": "vector"
        },
        {
            "id": "result2",
            "score": 0.7,
            "entity_type": "class",
            "source": "graph"
        },
        {
            "id": "result3",
            "score": 0.75,
            "entity_type": "function",
            "source": "both",
            "search_type": "definition"
        }
    ]
    
    ranked = answer_composer_agent._rank_results(results)
    
    assert len(ranked) == 3
    assert "rank_score" in ranked[0]
    assert "rank_score" in ranked[1]
    assert "rank_score" in ranked[2]
    
    # Results should be sorted by rank_score in descending order
    assert ranked[0]["rank_score"] >= ranked[1]["rank_score"]
    assert ranked[1]["rank_score"] >= ranked[2]["rank_score"]
    
    # The "both" source should have the highest score due to the boost
    assert ranked[0]["source"] == "both"


def test_generate_answer(answer_composer_agent):
    """Test _generate_answer method."""
    query = "How does authentication work?"
    query_analysis = {
        "intents": ["explanation"]
    }
    results = [
        {
            "entity_type": "function",
            "entity_id": "authenticate_user",
            "file_path": "/src/auth.py",
            "search_type": "definition"
        }
    ]
    
    answer = answer_composer_agent._generate_answer(query, query_analysis, results)
    
    assert isinstance(answer, str)
    assert len(answer) > 0
    assert "authenticate_user" in answer


def test_generate_definition_answer(answer_composer_agent):
    """Test _generate_definition_answer method."""
    query = "Where is authenticate_user defined?"
    results = [
        {
            "entity_type": "function",
            "entity_id": "authenticate_user",
            "file_path": "/src/auth.py",
            "start_line": 10,
            "search_type": "definition",
            "parameters": ["username", "password"]
        }
    ]
    
    answer = answer_composer_agent._generate_definition_answer(query, results)
    
    assert isinstance(answer, str)
    assert "authenticate_user" in answer
    assert "function" in answer.lower()
    assert "/src/auth.py" in answer
    assert "line 10" in answer
    assert "parameters" in answer.lower()


def test_generate_usage_answer(answer_composer_agent):
    """Test _generate_usage_answer method."""
    query = "Where is authenticate_user used?"
    results = [
        {
            "entity_type": "function",
            "entity_id": "authenticate_user",
            "file_path": "/src/login.py",
            "caller_type": "function",
            "caller_name": "login",
            "search_type": "usage"
        },
        {
            "entity_type": "function",
            "entity_id": "authenticate_user",
            "file_path": "/src/admin.py",
            "caller_type": "function",
            "caller_name": "admin_login",
            "search_type": "usage"
        }
    ]
    
    answer = answer_composer_agent._generate_usage_answer(query, results)
    
    assert isinstance(answer, str)
    assert "authenticate_user" in answer
    assert "2 usages" in answer
    assert "function" in answer.lower()
    assert "files" in answer.lower()


def test_select_code_snippets(answer_composer_agent):
    """Test _select_code_snippets method."""
    results = [
        {
            "entity_id": "authenticate_user",
            "entity_type": "function",
            "file_path": "/src/auth.py",
            "start_line": 10,
            "end_line": 20,
            "language": "python",
            "code_content": "def authenticate_user(username, password):\n    return True",
            "rank_score": 0.95
        },
        {
            "entity_id": "User",
            "entity_type": "class",
            "file_path": "/src/user.py",
            "start_line": 30,
            "end_line": 50,
            "language": "python",
            "code_content": "class User:\n    def __init__(self):\n        pass",
            "rank_score": 0.85
        },
        {
            "entity_id": "authenticate_user",  # Duplicate entity_id
            "entity_type": "function",
            "file_path": "/src/login.py",
            "start_line": 30,
            "end_line": 40,
            "language": "python",
            "code_content": "def login():\n    authenticate_user('user', 'pass')",
            "rank_score": 0.75
        }
    ]
    
    snippets = answer_composer_agent._select_code_snippets(results)
    
    assert len(snippets) <= answer_composer_agent.max_code_snippets
    assert snippets[0]["entity_id"] == "authenticate_user"
    assert snippets[1]["entity_id"] == "User"
    assert len(snippets) == 2  # Should not include duplicate entity_id
    
    # Each snippet should have required fields
    for snippet in snippets:
        assert "entity_id" in snippet
        assert "entity_type" in snippet
        assert "file_path" in snippet
        assert "language" in snippet
        assert "code" in snippet


def test_count_result_types(answer_composer_agent):
    """Test _count_result_types method."""
    results = [
        {
            "entity_type": "function",
            "search_type": "definition",
            "source": "vector"
        },
        {
            "entity_type": "class",
            "search_type": "definition",
            "source": "graph"
        },
        {
            "entity_type": "function",
            "search_type": "usage",
            "source": "both"
        }
    ]
    
    counts = answer_composer_agent._count_result_types(results)
    
    assert "entity_types" in counts
    assert "search_types" in counts
    assert "sources" in counts
    
    assert counts["entity_types"]["function"] == 2
    assert counts["entity_types"]["class"] == 1
    assert counts["search_types"]["definition"] == 2
    assert counts["search_types"]["usage"] == 1
    assert counts["sources"]["vector"] == 1
    assert counts["sources"]["graph"] == 1
    assert counts["sources"]["both"] == 1