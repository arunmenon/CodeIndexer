# Code Indexer Testing

This document describes the testing strategy for the Code Indexer project.

## Overview

The Code Indexer testing strategy includes three main types of tests:

1. **Unit Tests**: Testing individual components in isolation
2. **Integration Tests**: Testing interactions between components
3. **Benchmarks**: Testing performance and scaling

## Prerequisites

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

## Running Tests

### Running All Tests

```bash
pytest
```

### Running Specific Test Types

```bash
# Run only unit tests
pytest tests/unit

# Run only integration tests
pytest -m integration

# Run only benchmarks
pytest -m benchmark
```

### Running with Coverage

```bash
pytest --cov=code_indexer
```

## Test Structure

The tests are organized by type and component:

```
tests/
├── unit/                  # Unit tests
│   ├── tools/             # Tests for tools
│   ├── agents/            # Tests for agents
│   └── utils/             # Tests for utilities
├── integration/           # Integration tests
├── benchmark/             # Performance benchmarks
├── fixtures/              # Test fixtures
├── conftest.py            # Common fixtures and configurations
└── utils.py               # Test utilities
```

## Unit Tests

Unit tests verify that individual components work correctly in isolation. They use mocks to remove dependencies on other components.

### Vector Store Tests

Tests for the vector store abstraction and implementations:

- `test_vector_store_interface.py`: Tests for the vector store interface and common classes
- `test_milvus_vector_store.py`: Tests for the Milvus implementation
- `test_vector_store_factory.py`: Tests for the vector store factory
- `test_vector_store_utils.py`: Tests for vector store utilities

### Agent Tests

Tests for the agent components:

- `test_query_agent.py`: Tests for the query processing agent
- `test_vector_search_agent.py`: Tests for the vector search agent
- `test_graph_search_agent.py`: Tests for the graph search agent
- `test_answer_composer_agent.py`: Tests for the answer composition agent
- `test_search_orchestrator_agent.py`: Tests for the search orchestration agent

## Integration Tests

Integration tests verify that components work together correctly. They test the interactions between agents and tools.

The main integration test is `test_search_pipeline.py`, which tests the end-to-end search flow with actual agents (but mocked tools).

## Benchmarks

Benchmarks measure the performance of the system under different conditions. They are located in the `tests/benchmark` directory.

The main benchmark is `test_search_performance.py`, which tests:

- Search performance with different result sizes
- Search performance with different search types (hybrid, vector, graph)
- Query processing performance with different query complexities

Benchmark results are written to the `benchmark_results` directory as JSONL files.

## Mock Implementations

The tests use several mock implementations:

- **MockVectorStore**: A simple in-memory vector store for testing
- **MockGraph**: A simple in-memory graph for testing structural queries
- **MockAgentContext**: A mock implementation of the ADK agent context
- **MockEmbeddingTool**: A mock implementation of the embedding tool

## Test Fixtures

Common test fixtures are defined in `conftest.py` and include:

- **sample_code_chunk**: Sample code for testing
- **sample_embedding**: Sample embedding vector
- **sample_metadata**: Sample metadata for embeddings
- **mock_vector_store**: Mock vector store implementation
- **mock_agent_context**: Mock agent context
- **mock_neo4j_tool**: Mock Neo4j tool
- **mock_embedding_tool**: Mock embedding tool

## Adding New Tests

### Adding a Unit Test

1. Create a new test file in the appropriate directory (e.g., `tests/unit/tools/test_new_tool.py`)
2. Import the component to test
3. Define test functions with names starting with `test_`
4. Use assertions to verify the behavior

Example:

```python
def test_my_function():
    result = my_function(input_data)
    assert result == expected_output
```

### Adding an Integration Test

1. Create a new test file in the `tests/integration` directory
2. Add the `@pytest.mark.integration` decorator to your test functions
3. Set up the required components and their connections
4. Verify the end-to-end behavior

### Adding a Benchmark

1. Create a new test file in the `tests/benchmark` directory
2. Add the `@pytest.mark.benchmark` decorator to your test functions
3. Measure performance metrics (e.g., execution time)
4. Save benchmark results to the `benchmark_results` directory

## Continuous Integration

Tests are automatically run in CI for each pull request and merge to main. The CI configuration includes:

- Running all unit tests
- Running integration tests
- Checking code coverage
- Running lint checks

Benchmarks are not run in CI to avoid performance variations due to different environments.