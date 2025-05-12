"""
Tests for the QueryAgent.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.agents.query_agent import QueryAgent

from google.adk.api.agent import AgentContext, HandlerResponse
from google.adk.api.tool import ToolResponse


@pytest.fixture
def mock_agent_context():
    """Mock agent context for testing."""
    mock = MagicMock(spec=AgentContext)
    
    # Set up the get_tool method
    mock_embedding_tool = MagicMock()
    
    # Configure embedding tool responses
    def mock_generate_embedding(params):
        mock_response = MagicMock(spec=ToolResponse)
        mock_response.status.is_success.return_value = True
        
        # Generate deterministic embedding
        np.random.seed(42)
        mock_response.data = {
            "embedding": np.random.rand(64).tolist(),
            "model": "test-model"
        }
        return mock_response
    
    mock_embedding_tool.generate_embedding = mock_generate_embedding
    
    # Configure the get_tool response
    mock_tool_response = MagicMock()
    mock_tool_response.status.is_success.return_value = True
    mock_tool_response.tool = mock_embedding_tool
    
    mock.get_tool.return_value = mock_tool_response
    
    return mock


@pytest.fixture
def query_agent(mock_agent_context):
    """Create a QueryAgent instance for testing."""
    config = {
        "embedding_dimension": 64,
        "llm_model": "test-model",
        "multi_query_expansion": True,
        "expansion_count": 2
    }
    
    agent = QueryAgent(config)
    agent.init(mock_agent_context)
    
    return agent


def test_init(mock_agent_context):
    """Test QueryAgent initialization."""
    config = {
        "embedding_dimension": 128,
        "llm_model": "gpt-4",
        "multi_query_expansion": True,
        "expansion_count": 3
    }
    
    agent = QueryAgent(config)
    agent.init(mock_agent_context)
    
    assert agent.config == config
    assert agent.embedding_dimension == 128
    assert agent.llm_model == "gpt-4"
    assert agent.multi_query_expansion is True
    assert agent.expansion_count == 3
    assert agent.embedding_tool is not None
    mock_agent_context.get_tool.assert_called_once_with("embedding_tool")


def test_run_with_empty_query(query_agent):
    """Test run method with empty query."""
    response = query_agent.run({})
    
    assert isinstance(response, HandlerResponse)
    assert not response.status.is_success()
    assert "No query provided" in response.status.message


def test_run_with_query(query_agent):
    """Test run method with valid query."""
    response = query_agent.run({
        "query": "How does the authentication system work?",
        "search_type": "hybrid",
        "max_results": 10
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    assert "search_spec" in response.data
    
    search_spec = response.data["search_spec"]
    assert search_spec["original_query"] == "How does the authentication system work?"
    assert "analyzed_query" in search_spec
    assert "embeddings" in search_spec
    assert "primary" in search_spec["embeddings"]
    assert "expanded" in search_spec["embeddings"]
    assert search_spec["search_type"] == "hybrid"
    assert search_spec["max_results"] == 10


def test_detect_intent(query_agent):
    """Test _detect_intent method."""
    # Test definition intent
    intents = query_agent._detect_intent("Find the definition of authenticate_user")
    assert "definition" in intents
    
    # Test usage intent
    intents = query_agent._detect_intent("Where is authenticate_user used?")
    assert "usage" in intents
    
    # Test explanation intent
    intents = query_agent._detect_intent("How does the authentication system work?")
    assert "explanation" in intents
    
    # Test code generation intent
    intents = query_agent._detect_intent("Implement a login function")
    assert "generation" in intents
    
    # Test inheritance intent
    intents = query_agent._detect_intent("What classes inherit from BaseUser?")
    assert "inheritance" in intents
    
    # Test default intent
    intents = query_agent._detect_intent("Show me some code")
    assert "information" in intents


def test_extract_entities(query_agent):
    """Test _extract_entities method."""
    # Test function extraction
    entities = query_agent._extract_entities("Find the authenticate_user function")
    assert "authenticate_user" in entities["functions"]
    
    # Test class extraction
    entities = query_agent._extract_entities("Show me the UserManager class")
    assert "UserManager" in entities["classes"]
    
    # Test file extraction
    entities = query_agent._extract_entities("Look at the auth.py file")
    assert "auth.py" in entities["files"]


def test_generate_query_embeddings(query_agent):
    """Test _generate_query_embeddings method."""
    # Test generating embeddings
    embeddings = query_agent._generate_query_embeddings(
        "How does authentication work?",
        ["How does authentication work?"]
    )
    
    assert "primary" in embeddings
    assert len(embeddings["primary"]) > 0
    assert "expanded" in embeddings
    assert len(embeddings["expanded"]) > 0
    assert len(embeddings["expanded"]) <= query_agent.expansion_count


def test_expand_query(query_agent):
    """Test _expand_query method."""
    # Test query expansion
    expanded = query_agent._expand_query(
        "How does authentication work?",
        ["How does authentication work?"]
    )
    
    assert len(expanded) <= query_agent.expansion_count
    assert all(isinstance(q, str) for q in expanded)
    assert all(q != "How does authentication work?" for q in expanded)


def test_enhance_filters(query_agent):
    """Test _enhance_filters method."""
    # Test with empty filters
    user_filters = {}
    query_analysis = {
        "intents": ["definition"],
        "original_query": "Find Python functions"
    }
    
    # Mock the _detect_languages method
    with patch.object(query_agent, '_detect_languages', return_value=["python"]):
        enhanced = query_agent._enhance_filters(user_filters, query_analysis)
        
        assert "language" in enhanced
        assert enhanced["language"] == ["python"]
        assert "entity_type" in enhanced
        
    # Test with user-provided filters
    user_filters = {
        "language": "javascript",
        "file_path": "/src/auth.js"
    }
    
    enhanced = query_agent._enhance_filters(user_filters, query_analysis)
    
    assert enhanced["language"] == "javascript"  # User filter preserved
    assert enhanced["file_path"] == "/src/auth.js"  # User filter preserved