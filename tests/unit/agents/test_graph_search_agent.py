"""
Tests for the GraphSearchAgent.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.agents.graph_search_agent import GraphSearchAgent

from google.adk.api.agent import AgentContext, HandlerResponse
from google.adk.api.tool import ToolResponse


@pytest.fixture
def mock_neo4j_tool():
    """Create a mock Neo4j tool."""
    mock = MagicMock()
    
    # Configure execute_query method
    def mock_execute_query(params):
        query = params.get("query", "")
        mock_response = MagicMock(spec=ToolResponse)
        mock_response.status.is_success.return_value = True
        
        # Return different results based on the query
        if "Function" in query:
            mock_response.data = {
                "results": [
                    {
                        "func": {
                            "name": "authenticate_user",
                            "parameters": ["username", "password"],
                            "returnType": "boolean"
                        },
                        "filePath": "/src/auth.py",
                        "startLine": 10,
                        "endLine": 20,
                        "language": "python"
                    }
                ]
            }
        elif "CALLS" in query:
            mock_response.data = {
                "results": [
                    {
                        "caller": {
                            "name": "login"
                        },
                        "callerName": "login",
                        "filePath": "/src/login.py",
                        "startLine": 30,
                        "endLine": 40,
                        "language": "python",
                        "callerType": ["Function"]
                    }
                ]
            }
        elif "EXTENDS" in query:
            mock_response.data = {
                "results": [
                    {
                        "subclass": {
                            "name": "AdminUser"
                        },
                        "subclassName": "AdminUser",
                        "filePath": "/src/users.py",
                        "startLine": 50,
                        "endLine": 70,
                        "language": "python"
                    }
                ]
            }
        elif "IMPORTS" in query:
            mock_response.data = {
                "results": [
                    {
                        "file": {
                            "path": "/src/auth.py"
                        },
                        "filePath": "/src/auth.py",
                        "language": "python"
                    }
                ]
            }
        else:
            mock_response.data = {
                "results": []
            }
        
        return mock_response
    
    mock.execute_query.side_effect = mock_execute_query
    
    return mock


@pytest.fixture
def mock_agent_context(mock_neo4j_tool):
    """Mock agent context for testing."""
    mock = MagicMock(spec=AgentContext)
    
    # Configure the get_tool response for neo4j_tool
    mock_tool_response = MagicMock()
    mock_tool_response.status.is_success.return_value = True
    mock_tool_response.tool = mock_neo4j_tool
    
    mock.get_tool.return_value = mock_tool_response
    
    return mock


@pytest.fixture
def graph_search_agent(mock_agent_context):
    """Create a GraphSearchAgent instance for testing."""
    config = {
        "default_limit": 10,
        "neo4j_db": "neo4j"
    }
    
    agent = GraphSearchAgent(config)
    agent.init(mock_agent_context)
    
    return agent


def test_init(mock_agent_context):
    """Test GraphSearchAgent initialization."""
    config = {
        "default_limit": 5,
        "neo4j_db": "test_db"
    }
    
    agent = GraphSearchAgent(config)
    agent.init(mock_agent_context)
    
    assert agent.config == config
    assert agent.default_limit == 5
    assert agent.neo4j_db == "test_db"
    assert agent.neo4j_tool is not None
    mock_agent_context.get_tool.assert_called_once_with("neo4j_tool")


def test_run_with_empty_search_spec(graph_search_agent):
    """Test run method with empty search specification."""
    response = graph_search_agent.run({})
    
    assert isinstance(response, HandlerResponse)
    assert not response.status.is_success()
    assert "No search specification provided" in response.status.message


def test_run_with_definition_intent(graph_search_agent):
    """Test run method with definition intent."""
    response = graph_search_agent.run({
        "search_spec": {
            "analyzed_query": {
                "intents": ["definition"],
                "entities": {
                    "functions": ["authenticate_user"]
                }
            }
        },
        "max_results": 5
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    assert "results" in response.data
    assert "total_count" in response.data
    assert "query_type" in response.data
    assert response.data["query_type"] == "definition"
    assert len(response.data["results"]) > 0
    assert response.data["results"][0]["entity_id"] == "authenticate_user"
    assert response.data["results"][0]["file_path"] == "/src/auth.py"


def test_run_with_usage_intent(graph_search_agent):
    """Test run method with usage intent."""
    response = graph_search_agent.run({
        "search_spec": {
            "analyzed_query": {
                "intents": ["usage"],
                "entities": {
                    "functions": ["authenticate_user"]
                }
            }
        },
        "max_results": 5
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    assert "results" in response.data
    assert len(response.data["results"]) > 0
    assert response.data["query_type"] == "usage"
    assert response.data["results"][0]["caller_name"] == "login"
    assert response.data["results"][0]["file_path"] == "/src/login.py"


def test_run_with_inheritance_intent(graph_search_agent):
    """Test run method with inheritance intent."""
    response = graph_search_agent.run({
        "search_spec": {
            "analyzed_query": {
                "intents": ["inheritance"],
                "entities": {
                    "classes": ["User"]
                }
            }
        },
        "max_results": 5
    })
    
    assert isinstance(response, HandlerResponse)
    assert response.status.is_success()
    assert "results" in response.data
    assert len(response.data["results"]) > 0
    assert response.data["query_type"] == "inheritance"
    

def test_find_definitions(graph_search_agent, mock_neo4j_tool):
    """Test _find_definitions method."""
    entities = {
        "functions": ["authenticate_user"],
        "classes": []
    }
    
    results = graph_search_agent._find_definitions(entities, 5)
    
    assert len(results) > 0
    assert results[0]["entity_type"] == "function"
    assert results[0]["entity_id"] == "authenticate_user"
    assert results[0]["file_path"] == "/src/auth.py"
    assert "parameters" in results[0]
    assert "return_type" in results[0]
    mock_neo4j_tool.execute_query.assert_called_once()


def test_find_usages(graph_search_agent, mock_neo4j_tool):
    """Test _find_usages method."""
    entities = {
        "functions": ["authenticate_user"],
        "classes": []
    }
    
    results = graph_search_agent._find_usages(entities, 5)
    
    assert len(results) > 0
    assert results[0]["entity_type"] == "function"
    assert results[0]["entity_id"] == "authenticate_user"
    assert results[0]["caller_name"] == "login"
    assert results[0]["file_path"] == "/src/login.py"
    mock_neo4j_tool.execute_query.assert_called_once()


def test_find_inheritance_relationships(graph_search_agent, mock_neo4j_tool):
    """Test _find_inheritance_relationships method."""
    entities = {
        "classes": ["User"]
    }
    
    results = graph_search_agent._find_inheritance_relationships(entities, 5)
    
    assert len(results) > 0
    assert results[0]["entity_type"] == "class"
    assert results[0]["entity_id"] == "User"
    assert "relationship_type" in results[0]
    assert "related_entity" in results[0]
    mock_neo4j_tool.execute_query.assert_called()


def test_find_imports(graph_search_agent, mock_neo4j_tool):
    """Test _find_imports method."""
    entities = {
        "packages": ["auth"]
    }
    
    results = graph_search_agent._find_imports(entities, 5)
    
    assert len(results) > 0
    assert results[0]["entity_type"] == "package"
    assert results[0]["entity_id"] == "auth"
    assert results[0]["file_path"] == "/src/auth.py"
    mock_neo4j_tool.execute_query.assert_called_once()


def test_general_search(graph_search_agent, mock_neo4j_tool):
    """Test _general_search method."""
    query_analysis = {
        "original_query": "Find authenticate user function"
    }
    
    results = graph_search_agent._general_search(query_analysis, 5)
    
    # This calls Neo4j with potential identifiers extracted from the query
    mock_neo4j_tool.execute_query.assert_called()


def test_determine_query_type(graph_search_agent):
    """Test _determine_query_type method."""
    assert graph_search_agent._determine_query_type(["definition"]) == "definition"
    assert graph_search_agent._determine_query_type(["usage"]) == "usage"
    assert graph_search_agent._determine_query_type(["inheritance"]) == "inheritance"
    assert graph_search_agent._determine_query_type(["imports"]) == "import"
    assert graph_search_agent._determine_query_type(["other"]) == "general"