# CodeIndexer Codebase Structure

This document provides a detailed overview of the CodeIndexer project's directory structure, explaining the purpose and functionality of each major module.

## Directory Structure Overview

The codebase is organized into the following major directories:

```
code_indexer/
├── agents/         # LLM-powered agents for search and reasoning
├── api/            # REST API endpoints for search
├── cli/            # Command-line interfaces
├── config/         # Configuration files and settings
├── ingestion/      # Core code ingestion pipeline
├── models/         # Data models and schemas
├── semantic/       # Semantic understanding components
├── tools/          # Low-level utilities and integrations
└── utils/          # Helper functions and common utilities
```

## Module Descriptions

### `agents/`

The `agents` module contains LLM-powered agents that work together to provide intelligent code search and analysis capabilities.

**Key Components:**
- `answer_composer_agent.py`: Formats and composes final search results into coherent answers
- `code_parser_agent.py`: Extracts semantic information from code using LLMs
- `embedding_agent.py`: Generates vector embeddings for code chunks
- `git_ingestion_agent.py`: Handles repository cloning and file extraction
- `graph_builder_agent.py`: Constructs the code knowledge graph
- `graph_search_agent.py`: Executes specialized graph queries
- `query_agent.py`: Processes and expands user queries
- `search_orchestrator_agent.py`: Coordinates the overall search process
- `vector_search_agent.py`: Performs similarity searches using vector embeddings

**Use Case:** The agent system enables natural language code search, letting users ask questions like "How does the error handling work?" or "Find all API endpoints that access the database."

### `api/`

The `api` module provides REST API endpoints for programmatically accessing CodeIndexer's functionality.

**Key Components:**
- `search_api.py`: Exposes search endpoints for querying indexed codebases

**Use Case:** Allows integration of CodeIndexer into other tools, IDEs, or web interfaces through a standardized API.

### `cli/`

The `cli` module contains command-line interfaces for interacting with CodeIndexer.

**Key Components:**
- `search_cli.py`: Command-line interface for searching indexed code
- `run_remote_pipeline.py`: Runs the pipeline against remote repositories
- `direct_parse.py`: Direct parsing of local files for testing

**Use Case:** Provides developers with easy command-line tools to index and search codebases.

### `config/`

The `config` module handles configuration management for the system.

**Key Components:**
- `vector_store_config.yaml`: Configuration for vector databases

**Use Case:** Centralizes configuration settings for different components of the system.

### `ingestion/`

The `ingestion` module is the core of CodeIndexer, handling the entire process of extracting, parsing, and indexing code.

**Key Components:**
- `cli/`: Command-line interfaces specific to ingestion
  - `run_pipeline.py`: Main entry point for running the ingestion pipeline
- `direct/`: Direct implementation of ingestion components
  - `ast_extractor.py`: Extracts abstract syntax trees from code files
  - `code_parser.py`: Parses code files into structured formats
  - `git_ingestion.py`: Handles repository cloning and file extraction
  - `graph_builder.py`: Builds the code knowledge graph
  - `enhanced_graph_builder.py`: Advanced graph building with cross-file resolution
  - `neo4j_tool.py`: Interface to Neo4j database
- `stages/`: Modular pipeline stages
  - `git.py`: Git repository processing stage
  - `parse.py`: Code parsing stage
  - `graph.py`: Graph building stage
  - `chunk.py`: Code chunking stage
  - `embed.py`: Embedding generation stage
  - `dead_code.py`: Dead code detection stage
- `pipeline.py`: Core pipeline implementation
- `resilient_pipeline.py`: Error-tolerant pipeline with recovery mechanisms

**Use Case:** The ingestion module extracts meaningful information from code repositories, creating a structured representation that enables powerful search and analysis.

### `models/`

The `models` module contains data models and schemas used throughout the system.

**Key Components:**
- Data structures and schema definitions (future expansion)

**Use Case:** Provides consistent data structures for representing code entities across the system.

### `semantic/`

The `semantic` module handles higher-level semantic understanding of code.

**Key Components:**
- `api.py`: API for semantic code understanding
- `agents/`: Specialized semantic agents
- `teams/`: Team-based agent orchestration
- `tools/`: Semantic analysis tools

**Use Case:** Enables understanding of code at a conceptual level, beyond just syntax and structure.

### `tools/`

The `tools` module provides low-level utilities and integrations with external systems.

**Key Components:**
- `ast_extractor.py`: Core AST extraction functionality
- `code_chunking_tool.py`: Divides code into semantic chunks
- `embedding_tool.py`: Generates vector embeddings for code
- `git_tool.py`: Git operations and repository management
- `milvus_vector_store.py`: Integration with Milvus vector database
- `neo4j_tool.py`: Neo4j graph database integration
- `tree_sitter_parser.py`: Tree-sitter parsing implementation
- `vector_store_interface.py`: Abstract interface for vector stores
- `vector_store_factory.py`: Factory for creating vector store instances
- `tree-sitter-libs/`: Tree-sitter grammar libraries for different languages

**Use Case:** Provides the fundamental building blocks used by higher-level components in the system.

### `utils/`

The `utils` module contains helper functions and common utilities used throughout the codebase.

**Key Components:**
- `ast_utils.py`: Utilities for working with abstract syntax trees
- `ast_composite.py`: Composite pattern implementation for AST processing
- `ast_visitor.py`: Visitor pattern for traversing ASTs
- `ast_iterator.py`: Iterator for efficient AST traversal
- `batch_processor.py`: Batch processing of large datasets
- `error_handler.py`: Error handling and reporting
- `graph_commands.py`: Neo4j graph commands and queries
- `indexing_observer.py`: Observer pattern for indexing events
- `neo4j_batch.py`: Batched operations for Neo4j
- `pipeline_error_handling.py`: Error handling specific to the pipeline
- `repo_utils.py`: Repository utility functions
- `vector_store_utils.py`: Utilities for vector store operations

**Use Case:** Provides common functionality needed across multiple components, promoting code reuse and consistency.

## Cross-Component Interactions

The CodeIndexer system follows a layered architecture with clear dependencies:

1. **Foundation Layer**: `tools/` and `utils/` provide fundamental building blocks
2. **Core Layer**: `ingestion/` implements the main processing pipeline
3. **Interface Layer**: `api/` and `cli/` provide user interfaces
4. **Intelligence Layer**: `agents/` and `semantic/` add AI-powered capabilities

## Major Data Flows

1. **Code Ingestion Flow**:
   ```
   git_tool → ast_extractor → tree_sitter_parser → graph_builder → neo4j_tool
   ```

2. **Search Flow**:
   ```
   query_agent → search_orchestrator → [graph_search_agent, vector_search_agent] → answer_composer_agent
   ```

3. **Incremental Update Flow**:
   ```
   git_tool (detect changes) → pipeline (process only changed files) → graph_builder (update graph)
   ```

## Extension Points

CodeIndexer is designed to be extensible in several key areas:

1. **Language Support**: Add new language parsers in `tools/` directory
2. **Vector Stores**: Implement new `vector_store_interface.py` implementations
3. **Graph Strategies**: Add new resolution strategies in `enhanced_graph_builder.py`
4. **Pipeline Stages**: Create new stages in `ingestion/stages/`
5. **Agents**: Add specialized agents in `agents/` directory

## Configuration and Customization

The system can be configured and customized through:

1. **Command-line arguments**: See `cli/` modules
2. **Configuration files**: See `config/` directory
3. **Environment variables**: For sensitive settings like database credentials

## Testing

Each module includes corresponding test files that validate its functionality:

- Unit tests verify individual components
- Integration tests check cross-component interactions
- End-to-end tests validate complete workflows

## Development Workflow

When extending CodeIndexer:

1. Start with the relevant interface in higher-level modules
2. Implement required functionality in lower-level modules
3. Update pipeline stages if needed
4. Extend CLI or API endpoints to expose new functionality
5. Add appropriate tests at all levels