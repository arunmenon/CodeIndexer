"""
Integration test for the end-to-end code indexing and search pipeline.

This test verifies that the entire pipeline works correctly, from Git ingestion
through AST parsing, graph building, chunking, embedding, and search.
"""

import os
import tempfile
import pytest
import time
import hashlib
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

# Import agents and tools
from code_indexer.agents.git_ingestion_agent import GitIngestionAgent
from code_indexer.agents.code_parser_agent import CodeParserAgent
from code_indexer.agents.graph_builder_agent import GraphBuilderAgent
from code_indexer.agents.chunker_agent import ChunkerAgent
from code_indexer.agents.embedding_agent import EmbeddingAgent
from code_indexer.agents.vector_store_agent import VectorStoreAgent
from code_indexer.agents.query_agent import QueryAgent
from code_indexer.agents.vector_search_agent import VectorSearchAgent
from code_indexer.agents.graph_search_agent import GraphSearchAgent
from code_indexer.agents.answer_composer_agent import AnswerComposerAgent
from code_indexer.agents.search_orchestrator_agent import SearchOrchestratorAgent
from code_indexer.agents.dead_code_detector_agent import DeadCodeDetectorAgent

from code_indexer.tools.git_tool import GitTool
from code_indexer.tools.ast_extractor import ASTExtractorTool
from code_indexer.tools.neo4j_tool import Neo4jTool
from code_indexer.tools.embedding_tool import EmbeddingTool
from code_indexer.tools.milvus_vector_store import MilvusVectorStore

# Import test utilities
from tests.utils import create_sample_repo


@pytest.fixture(scope="module")
def mock_agent_context():
    """Create a mock agent context with all required tools."""
    mock = MagicMock()
    
    # Set up mock tools
    mock_git_tool = MagicMock()
    mock_git_tool.clone_repository.return_value = (True, "/path/to/repo")
    mock_git_tool.get_changed_files.return_value = {"file1.py": "A", "file2.py": "M"}
    mock_git_tool.get_file_content.return_value = "def sample_function(): pass"
    
    mock_ast_extractor = MagicMock()
    mock_ast_extractor.extract_ast.return_value = {
        "language": "python",
        "root": {
            "type": "Module",
            "children": [
                {
                    "type": "FunctionDef",
                    "attributes": {"name": "sample_function"},
                    "start_position": {"row": 1, "column": 0},
                    "end_position": {"row": 1, "column": 30},
                    "children": []
                }
            ]
        }
    }
    
    mock_neo4j_tool = MagicMock()
    mock_neo4j_tool.execute_query.return_value = MagicMock(
        status=MagicMock(is_success=lambda: True),
        data={"results": []}
    )
    
    mock_embedding_tool = MagicMock()
    mock_embedding_tool.generate_embedding.return_value = MagicMock(
        status=MagicMock(is_success=lambda: True),
        data={"embedding": [0.1, 0.2, 0.3]}
    )
    
    mock_vector_store = MagicMock()
    mock_vector_store.insert.return_value = ["id1", "id2"]
    mock_vector_store.search.return_value = [
        {"id": "id1", "score": 0.95, "metadata": {"file_path": "/src/sample.py"}}
    ]
    
    # Configure get_tool to return the appropriate mock
    def get_mock_tool(tool_name):
        tool_map = {
            "git_tool": mock_git_tool,
            "ast_extractor_tool": mock_ast_extractor,
            "neo4j_tool": mock_neo4j_tool,
            "embedding_tool": mock_embedding_tool,
            "vector_store": mock_vector_store
        }
        
        tool = tool_map.get(tool_name, MagicMock())
        return MagicMock(
            status=MagicMock(is_success=lambda: True),
            tool=tool
        )
    
    mock.get_tool.side_effect = get_mock_tool
    mock.state = {}
    
    return mock


@pytest.fixture
def ingestion_pipeline(mock_agent_context):
    """Initialize and connect the ingestion pipeline agents."""
    
    git_config = {
        "repositories": [{"url": "https://github.com/example/repo", "branch": "main"}],
        "polling_interval": 3600
    }
    
    code_parser_config = {
        "max_file_size": 1024 * 1024,
        "batch_size": 10
    }
    
    graph_builder_config = {
        "use_imports": True,
        "use_inheritance": True,
        "detect_calls": True
    }
    
    chunker_config = {
        "max_chunk_size": 1024,
        "min_chunk_size": 64,
        "overlap": 50
    }
    
    embedding_config = {
        "batch_size": 10,
        "model": "sentence-transformers/all-MiniLM-L6-v2"
    }
    
    vector_store_config = {
        "default_collection": "code_embeddings",
        "embedding_dimension": 384,
        "batch_size": 100
    }
    
    # Initialize agents
    git_agent = GitIngestionAgent(git_config)
    code_parser_agent = CodeParserAgent(code_parser_config)
    graph_builder_agent = GraphBuilderAgent(graph_builder_config)
    chunker_agent = ChunkerAgent()
    embedding_agent = EmbeddingAgent()
    vector_store_agent = VectorStoreAgent()
    
    # Initialize agents with context
    git_agent.init(mock_agent_context)
    code_parser_agent.init(mock_agent_context)
    graph_builder_agent.init(mock_agent_context)
    
    # Modify the context to return the real agents
    def get_agent(tool_name):
        agent_map = {
            "code_parser_agent": code_parser_agent,
            "graph_builder_agent": graph_builder_agent
        }
        
        agent = agent_map.get(tool_name)
        if agent:
            return MagicMock(
                status=MagicMock(is_success=lambda: True),
                tool=agent
            )
        
        # Fall back to mock context
        return mock_agent_context.get_tool(tool_name)
    
    git_context = MagicMock()
    git_context.get_tool.side_effect = get_agent
    git_context.state = {}
    
    return {
        "git_agent": git_agent,
        "git_context": git_context,
        "code_parser_agent": code_parser_agent,
        "graph_builder_agent": graph_builder_agent,
        "chunker_agent": chunker_agent,
        "embedding_agent": embedding_agent,
        "vector_store_agent": vector_store_agent
    }


@pytest.fixture
def search_pipeline(mock_agent_context):
    """Initialize and connect the search pipeline agents."""
    
    query_config = {
        "embedding_dimension": 384,
        "multi_query_expansion": True,
        "expansion_count": 3
    }
    
    vector_search_config = {
        "default_collection": "code_embeddings",
        "default_top_k": 10,
        "minimum_score": 0.7
    }
    
    graph_search_config = {
        "default_limit": 10,
        "neo4j_db": "neo4j"
    }
    
    answer_composer_config = {
        "max_code_snippets": 3,
        "include_explanations": True,
        "answer_style": "concise"
    }
    
    orchestrator_config = {
        "search_types": ["hybrid"],
        "enable_parallel": True,
        "vector_store_collection": "code_embeddings"
    }
    
    dead_code_config = {
        "ignore_entry_points": True,
        "ignore_tests": True,
        "max_results": 100
    }
    
    # Initialize agents
    query_agent = QueryAgent(query_config)
    vector_search_agent = VectorSearchAgent(vector_search_config)
    graph_search_agent = GraphSearchAgent(graph_search_config)
    answer_composer_agent = AnswerComposerAgent(answer_composer_config)
    orchestrator_agent = SearchOrchestratorAgent(orchestrator_config)
    dead_code_agent = DeadCodeDetectorAgent(dead_code_config)
    
    # Initialize with context
    query_agent.init(mock_agent_context)
    vector_search_agent.init(mock_agent_context)
    graph_search_agent.init(mock_agent_context)
    answer_composer_agent.init(mock_agent_context)
    
    # Create a context for the orchestrator that returns the actual agents
    def get_search_agent(tool_name):
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
        
        # Fall back to the mock_agent_context
        return mock_agent_context.get_tool(tool_name)
    
    orchestrator_context = MagicMock()
    orchestrator_context.get_tool.side_effect = get_search_agent
    orchestrator_context.state = {}
    
    orchestrator_agent.init(orchestrator_context)
    dead_code_agent.init(mock_agent_context)
    
    return {
        "query_agent": query_agent,
        "vector_search_agent": vector_search_agent,
        "graph_search_agent": graph_search_agent,
        "answer_composer_agent": answer_composer_agent,
        "orchestrator_agent": orchestrator_agent,
        "orchestrator_context": orchestrator_context,
        "dead_code_agent": dead_code_agent
    }


@pytest.mark.integration
def test_ingestion_pipeline(ingestion_pipeline):
    """Test the full ingestion pipeline."""
    # Create a sample repository
    with tempfile.TemporaryDirectory() as temp_dir:
        sample_files = create_sample_repo(temp_dir)
        
        # Configure the git agent to process the sample repository
        git_agent = ingestion_pipeline["git_agent"]
        git_context = ingestion_pipeline["git_context"]
        
        # Mock the Git tool to use the real temp directory
        git_tool_mock = git_context.get_tool("git_tool").tool
        git_tool_mock.clone_repository.return_value = (True, temp_dir)
        git_tool_mock.get_file_content.side_effect = lambda repo_path, file_path, commit=None: open(os.path.join(repo_path, file_path), 'r').read()
        
        # Mock the git_tool.get_changed_files to return all sample files
        changed_files = {os.path.relpath(path, temp_dir): "A" for path in sample_files.values()}
        git_tool_mock.get_changed_files.return_value = changed_files
        git_tool_mock.filter_indexable_files.return_value = list(changed_files.keys())
        
        # Run the git agent to start the ingestion pipeline
        response = git_agent.run({
            "repositories": [{"url": temp_dir, "name": "test_repo"}],
            "mode": "full"
        })
        
        # Verify the response
        assert response.status.is_success()
        assert "results" in response.data
        assert len(response.data["results"]) > 0
        
        # Check that files were processed
        first_result = response.data["results"][0]
        assert first_result["status"] == "success"
        assert first_result["files_detected"] > 0
        assert "files_processed" in first_result
        
        # The pipeline is mocked, so we're just verifying the flow rather than actual processing


@pytest.mark.integration
def test_search_pipeline(search_pipeline):
    """Test the search pipeline."""
    orchestrator_agent = search_pipeline["orchestrator_agent"]
    
    # Run a search query
    response = orchestrator_agent.run({
        "query": "How does the calculator class work?",
        "search_type": "hybrid",
        "max_results": 5
    })
    
    # Verify the response
    assert response.status.is_success()
    assert "answer" in response.data
    assert "code_snippets" in response.data
    assert "query" in response.data
    assert "search_spec" in response.data
    assert "vector_results" in response.data
    assert "graph_results" in response.data
    
    # Check that the query was processed correctly
    assert response.data["query"] == "How does the calculator class work?"


@pytest.mark.integration
def test_dead_code_detection(search_pipeline):
    """Test dead code detection."""
    dead_code_agent = search_pipeline["dead_code_agent"]
    
    # Run dead code detection
    response = dead_code_agent.run({
        "scope": "all",
        "exclude_patterns": ["__.*__"]
    })
    
    # Verify the response
    assert response.status.is_success()
    assert "results" in response.data
    assert "total_results" in response.data
    assert "repository" in response.data
    assert "scope" in response.data
    assert "timestamp" in response.data


@pytest.mark.integration
def test_end_to_end_pipeline(ingestion_pipeline, search_pipeline):
    """Test the entire pipeline from ingestion to search."""
    # Create a sample repository
    with tempfile.TemporaryDirectory() as temp_dir:
        sample_files = create_sample_repo(temp_dir)
        
        # Configure the git agent to process the sample repository
        git_agent = ingestion_pipeline["git_agent"]
        git_context = ingestion_pipeline["git_context"]
        
        # Mock tools to use the sample repo
        git_tool_mock = git_context.get_tool("git_tool").tool
        git_tool_mock.clone_repository.return_value = (True, temp_dir)
        git_tool_mock.get_file_content.side_effect = lambda repo_path, file_path, commit=None: open(os.path.join(repo_path, file_path), 'r').read()
        
        # Mock changed files to include all sample files
        changed_files = {os.path.relpath(path, temp_dir): "A" for path in sample_files.values()}
        git_tool_mock.get_changed_files.return_value = changed_files
        git_tool_mock.filter_indexable_files.return_value = list(changed_files.keys())
        
        # 1. Run ingestion
        ingestion_response = git_agent.run({
            "repositories": [{"url": temp_dir, "name": "test_repo"}],
            "mode": "full"
        })
        assert ingestion_response.status.is_success()
        
        # 2. Run search
        orchestrator_agent = search_pipeline["orchestrator_agent"]
        search_response = orchestrator_agent.run({
            "query": "What does the sample class do?",
            "search_type": "hybrid",
            "max_results": 5
        })
        
        assert search_response.status.is_success()
        assert "answer" in search_response.data
        
        # 3. Run dead code detection
        dead_code_agent = search_pipeline["dead_code_agent"]
        detection_response = dead_code_agent.run({
            "repository": "test_repo",
            "scope": "all"
        })
        
        assert detection_response.status.is_success()
        assert "results" in detection_response.data


# Optional: Add a benchmark test to measure pipeline performance
@pytest.mark.benchmark
def test_search_performance(search_pipeline):
    """Benchmark search performance."""
    orchestrator_agent = search_pipeline["orchestrator_agent"]
    
    # Prepare test queries
    test_queries = [
        "How does the calculator work?",
        "What is the SampleClass used for?",
        "Find all functions that add numbers",
        "How are values stored in the class?",
        "What methods are available in the sample class?"
    ]
    
    # Measure search time
    start_time = time.time()
    
    for query in test_queries:
        response = orchestrator_agent.run({
            "query": query,
            "search_type": "hybrid",
            "max_results": 5
        })
        assert response.status.is_success()
    
    end_time = time.time()
    
    # Calculate average query time
    avg_query_time = (end_time - start_time) / len(test_queries)
    
    # This is just logging, not an actual assertion
    print(f"Average query time: {avg_query_time:.4f} seconds")
    
    # Ensure queries complete in a reasonable time (adjust based on real performance)
    assert avg_query_time < 10.0, f"Average query time too slow: {avg_query_time:.4f} seconds"