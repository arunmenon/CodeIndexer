"""
Integration tests for the search pipeline.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.agents.query_agent import QueryAgent
from code_indexer.agents.vector_search_agent import VectorSearchAgent
from code_indexer.agents.graph_search_agent import GraphSearchAgent
from code_indexer.agents.answer_composer_agent import AnswerComposerAgent
from code_indexer.agents.search_orchestrator_agent import SearchOrchestratorAgent

from tests.utils import create_sample_repo


@pytest.fixture(scope="module")
def mock_agent_context():
    """Create a mock agent context with all required tools."""
    mock = MagicMock()
    
    # Set up mock tools
    mock_embedding_tool = MagicMock()
    mock_embedding_tool.generate_embedding.return_value = MagicMock(
        status=MagicMock(is_success=lambda: True),
        data={"embedding": [0.1, 0.2, 0.3]}
    )
    
    mock_vector_store_agent = MagicMock()
    mock_vector_store_agent.search.return_value = MagicMock(
        status=MagicMock(is_success=lambda: True),
        data={"results": []}
    )
    
    mock_neo4j_tool = MagicMock()
    mock_neo4j_tool.execute_query.return_value = MagicMock(
        status=MagicMock(is_success=lambda: True),
        data={"results": []}
    )
    
    # Configure get_tool to return the appropriate mock
    def get_mock_tool(tool_name):
        tool_map = {
            "embedding_tool": mock_embedding_tool,
            "vector_store_agent": mock_vector_store_agent,
            "neo4j_tool": mock_neo4j_tool
        }
        
        tool = tool_map.get(tool_name, MagicMock())
        return MagicMock(
            status=MagicMock(is_success=lambda: True),
            tool=tool
        )
    
    mock.get_tool.side_effect = get_mock_tool
    
    return mock


@pytest.fixture
def search_agents(mock_agent_context):
    """Create instances of all search agents."""
    query_agent = QueryAgent({
        "embedding_dimension": 64,
        "multi_query_expansion": True
    })
    query_agent.init(mock_agent_context)
    
    vector_search_agent = VectorSearchAgent({
        "default_collection": "code_embeddings",
        "minimum_score": 0.7
    })
    vector_search_agent.init(mock_agent_context)
    
    graph_search_agent = GraphSearchAgent({
        "default_limit": 10
    })
    graph_search_agent.init(mock_agent_context)
    
    answer_composer_agent = AnswerComposerAgent({
        "max_code_snippets": 3,
        "include_explanations": True
    })
    answer_composer_agent.init(mock_agent_context)
    
    search_orchestrator_agent = SearchOrchestratorAgent({
        "search_types": ["hybrid", "vector", "graph"],
        "enable_parallel": True,
        "vector_store_collection": "code_embeddings"
    })
    
    # Patch the get_tool method to return the real agent instances
    def get_agent(tool_name):
        agent_map = {
            "query_agent": query_agent,
            "vector_search_agent": vector_search_agent,
            "graph_search_agent": graph_search_agent,
            "answer_composer_agent": answer_composer_agent
        }
        
        agent = agent_map.get(tool_name)
        if agent:
            return MagicMock(
                status=MagicMock(is_success=lambda: True),
                tool=agent
            )
        
        # Fall back to the mock_agent_context implementation
        return mock_agent_context.get_tool(tool_name)
    
    mock_context = MagicMock()
    mock_context.get_tool.side_effect = get_agent
    
    search_orchestrator_agent.init(mock_context)
    
    return {
        "query_agent": query_agent,
        "vector_search_agent": vector_search_agent,
        "graph_search_agent": graph_search_agent,
        "answer_composer_agent": answer_composer_agent,
        "search_orchestrator_agent": search_orchestrator_agent
    }


@pytest.mark.integration
def test_end_to_end_search_flow(search_agents):
    """Test the end-to-end search flow with actual agents (but mocked tools)."""
    # Create a temporary sample repository
    with tempfile.TemporaryDirectory() as temp_dir:
        create_sample_repo(temp_dir)
        
        # Run a search query
        response = search_agents["search_orchestrator_agent"].run({
            "query": "How does authentication work?",
            "search_type": "hybrid",
            "max_results": 5
        })
        
        # Check that the search was successful
        assert response.status.is_success()
        
        # Check that the response contains the expected fields
        assert "answer" in response.data
        assert "code_snippets" in response.data
        assert "query" in response.data
        assert "search_spec" in response.data
        assert "vector_results" in response.data
        assert "graph_results" in response.data
        assert "total_results" in response.data
        
        # Check that the query was passed through correctly
        assert response.data["query"] == "How does authentication work?"