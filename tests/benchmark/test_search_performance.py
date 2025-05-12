"""
Benchmarking tests for search performance.
"""

import pytest
import time
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

from code_indexer.agents.query_agent import QueryAgent
from code_indexer.agents.vector_search_agent import VectorSearchAgent
from code_indexer.agents.graph_search_agent import GraphSearchAgent
from code_indexer.agents.answer_composer_agent import AnswerComposerAgent
from code_indexer.agents.search_orchestrator_agent import SearchOrchestratorAgent

from tests.utils import create_sample_repo, generate_sample_embeddings, generate_sample_metadata


@pytest.fixture
def mock_agent_context():
    """Create a mock agent context with all required tools."""
    mock = MagicMock()
    
    # Set up mock tools with configurable response sizes
    def create_mock_embedding_tool(vector_size=64):
        mock_tool = MagicMock()
        
        def generate_embedding(params):
            import numpy as np
            np.random.seed(42)
            
            response = MagicMock()
            response.status.is_success.return_value = True
            response.data = {
                "embedding": np.random.rand(vector_size).tolist(),
                "model": "test-model"
            }
            return response
        
        mock_tool.generate_embedding.side_effect = generate_embedding
        return mock_tool
    
    def create_mock_vector_store_agent(result_count=10):
        mock_agent = MagicMock()
        
        def search(params):
            import numpy as np
            np.random.seed(42)
            
            # Generate sample results
            results = []
            for i in range(result_count):
                results.append({
                    "id": f"result{i}",
                    "score": 0.95 - (i * 0.01),
                    "metadata": {
                        "file_path": f"/src/file{i}.py",
                        "language": "python",
                        "entity_type": "function",
                        "entity_id": f"function{i}",
                        "start_line": i * 10,
                        "end_line": i * 10 + 10,
                        "chunk_id": f"chunk{i}"
                    }
                })
            
            response = MagicMock()
            response.status.is_success.return_value = True
            response.data = {
                "results": results,
                "total_count": len(results)
            }
            return response
        
        mock_agent.search.side_effect = search
        return mock_agent
    
    def create_mock_neo4j_tool(result_count=10):
        mock_tool = MagicMock()
        
        def execute_query(params):
            # Generate sample results based on the query
            results = []
            for i in range(result_count):
                results.append({
                    "func": {
                        "name": f"function{i}",
                        "parameters": ["param1", "param2"],
                        "returnType": "boolean"
                    },
                    "filePath": f"/src/file{i}.py",
                    "startLine": i * 10,
                    "endLine": i * 10 + 10,
                    "language": "python"
                })
            
            response = MagicMock()
            response.status.is_success.return_value = True
            response.data = {
                "results": results
            }
            return response
        
        mock_tool.execute_query.side_effect = execute_query
        return mock_tool
    
    # Create the mock tools
    mock_embedding_tool = create_mock_embedding_tool()
    mock_vector_store_agent = create_mock_vector_store_agent()
    mock_neo4j_tool = create_mock_neo4j_tool()
    
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


def create_search_agent(mock_agent_context, result_size=10):
    """Create a search orchestrator agent with the specified result size."""
    # Create the individual agents
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
        "default_limit": result_size
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
    
    return search_orchestrator_agent


class TestSearchPerformance:
    """Benchmark tests for search performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.parametrize("result_size", [10, 50, 100])
    def test_search_performance_by_result_size(self, mock_agent_context, result_size):
        """Test search performance with different result sizes."""
        # Create a search agent with the specified result size
        search_agent = create_search_agent(mock_agent_context, result_size)
        
        # Run the search and measure time
        start_time = time.time()
        
        response = search_agent.run({
            "query": "How does authentication work?",
            "search_type": "hybrid",
            "max_results": result_size
        })
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Print performance metrics
        print(f"\nSearch with {result_size} results:")
        print(f"  Time: {duration:.4f} seconds")
        print(f"  Success: {response.status.is_success()}")
        print(f"  Total results: {response.data.get('total_results', 0)}")
        
        # Ensure the search was successful
        assert response.status.is_success()
        assert response.data.get("total_results", 0) > 0
        
        # Write performance data to a file
        perf_data = {
            "test": "search_by_result_size",
            "result_size": result_size,
            "duration_seconds": duration,
            "total_results": response.data.get("total_results", 0),
        }
        
        # Create benchmark directory if it doesn't exist
        os.makedirs("benchmark_results", exist_ok=True)
        
        # Append to results file
        with open("benchmark_results/search_performance.jsonl", "a") as f:
            f.write(json.dumps(perf_data) + "\n")
    
    @pytest.mark.benchmark
    @pytest.mark.parametrize("search_type", ["hybrid", "vector", "graph"])
    def test_search_performance_by_type(self, mock_agent_context, search_type):
        """Test search performance with different search types."""
        # Create a search agent
        search_agent = create_search_agent(mock_agent_context)
        
        # Run the search and measure time
        start_time = time.time()
        
        response = search_agent.run({
            "query": "How does authentication work?",
            "search_type": search_type,
            "max_results": 50
        })
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Print performance metrics
        print(f"\nSearch type '{search_type}':")
        print(f"  Time: {duration:.4f} seconds")
        print(f"  Success: {response.status.is_success()}")
        
        # Count results by type
        vector_count = len(response.data.get("vector_results", []))
        graph_count = len(response.data.get("graph_results", []))
        print(f"  Vector results: {vector_count}")
        print(f"  Graph results: {graph_count}")
        
        # Ensure the search was successful
        assert response.status.is_success()
        
        # Write performance data to a file
        perf_data = {
            "test": "search_by_type",
            "search_type": search_type,
            "duration_seconds": duration,
            "vector_result_count": vector_count,
            "graph_result_count": graph_count,
        }
        
        # Create benchmark directory if it doesn't exist
        os.makedirs("benchmark_results", exist_ok=True)
        
        # Append to results file
        with open("benchmark_results/search_performance.jsonl", "a") as f:
            f.write(json.dumps(perf_data) + "\n")
    
    @pytest.mark.benchmark
    def test_query_processing_performance(self, mock_agent_context):
        """Test query processing performance."""
        # Create a query agent
        query_agent = QueryAgent({
            "embedding_dimension": 64,
            "multi_query_expansion": True,
            "expansion_count": 3
        })
        query_agent.init(mock_agent_context)
        
        # Define test queries of different complexities
        queries = [
            "Find the authenticate function",
            "How does the authentication system work?",
            "Find all Python functions related to user authentication that use database connections",
            "What classes inherit from the BaseUser class and how are they used in the authentication system?"
        ]
        
        for query in queries:
            # Run the query and measure time
            start_time = time.time()
            
            response = query_agent.run({
                "query": query
            })
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Print performance metrics
            query_length = len(query)
            print(f"\nQuery ({query_length} chars): {query}")
            print(f"  Time: {duration:.4f} seconds")
            print(f"  Success: {response.status.is_success()}")
            
            # Analyze the query
            if response.status.is_success():
                analyzed_query = response.data.get("search_spec", {}).get("analyzed_query", {})
                intents = analyzed_query.get("intents", [])
                entities = analyzed_query.get("entities", {})
                
                print(f"  Intents: {intents}")
                print(f"  Entities: {len(entities)}")
                
                # Count expanded queries
                expanded = response.data.get("search_spec", {}).get("embeddings", {}).get("expanded", [])
                print(f"  Expanded queries: {len(expanded)}")
            
            # Ensure the query processing was successful
            assert response.status.is_success()
            
            # Write performance data to a file
            perf_data = {
                "test": "query_processing",
                "query": query,
                "query_length": query_length,
                "duration_seconds": duration,
                "intents": intents if response.status.is_success() else [],
                "entity_count": len(entities) if response.status.is_success() else 0,
                "expanded_count": len(expanded) if response.status.is_success() else 0
            }
            
            # Create benchmark directory if it doesn't exist
            os.makedirs("benchmark_results", exist_ok=True)
            
            # Append to results file
            with open("benchmark_results/query_performance.jsonl", "a") as f:
                f.write(json.dumps(perf_data) + "\n")