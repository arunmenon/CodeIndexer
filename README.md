# CodeIndexer

A powerful, scalable code indexing and search system built with a modular architecture.

## Overview

CodeIndexer creates a semantic understanding of codebases by combining AST parsing, graph representation, and vector embeddings to enable natural language search and analysis of code.

**New to CodeIndexer?** Check out our [Getting Started Guide](docs/getting_started.md) to set up your environment and run your first indexing job.

## Key Features

- **Multi-Language Support**: Parses 50+ programming languages using Tree-sitter
- **Code Knowledge Graph**: Creates a graph representation of code structure and relationships
- **Cross-File Resolution**: Accurately tracks function calls and imports across files
- **Incremental Updates**: Efficiently processes code changes without full reindexing
- **Scalable Architecture**: Handles repositories of any size with optimized strategies

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/CodeIndexer.git
cd CodeIndexer

# Install dependencies
pip install -e .

# Process a local repository
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/local/repo --output-dir ./output

# Or process a remote repository (GitHub, GitLab, etc.)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/repo.git --output-dir ./output
```

## Architecture

CodeIndexer follows a modular pipeline architecture:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Git Ingestion  │────▶│  Code Parsing   │────▶│ Graph Building  │────▶│    Chunking     │────▶│    Embedding    │
│                 │     │                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

Each stage can be run independently or as part of an end-to-end process:

1. **Git Ingestion**: Extracts code from repositories with incremental update support
2. **Code Parsing**: Generates AST representations using Tree-sitter
3. **Graph Building**: Creates a knowledge graph in Neo4j with the placeholder pattern
4. **Chunking**: Divides code into semantic chunks
5. **Embedding**: Generates vector representations for similarity search

For detailed information, see [Ingestion Flow Documentation](docs/ingestion-flow.md).

## Project Structure

The codebase is organized into the following major modules:

- **`agents/`**: LLM-powered agents for intelligent code search and reasoning
- **`api/`**: REST API endpoints for programmatic access to search functionality
- **`cli/`**: Command-line interfaces for indexing and searching code
- **`config/`**: Configuration files and settings management
- **`ingestion/`**: Core pipeline for code extraction, parsing, and indexing
- **`models/`**: Data models and schema definitions
- **`semantic/`**: Components for higher-level semantic understanding of code
- **`tools/`**: Low-level utilities and integrations with external systems
- **`utils/`**: Helper functions and common utilities used throughout the codebase

For a detailed breakdown of each module, see the [Codebase Structure Documentation](docs/codebase_structure.md).

## Usage

### Basic Commands

```bash
# Index a local repository
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/local/repo --output-dir ./output

# Index a remote repository (GitHub, GitLab, etc.)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/repo.git --output-dir ./output

# Specify branch (default is 'main')
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/repo.git --branch develop --output-dir ./output

# Force full reindexing (instead of incremental)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --full-indexing --output-dir ./output

# Enable verbose logging
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --verbose --output-dir ./output
```

### Selective Processing

```bash
# Skip Git ingestion (use previously ingested files)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-git --output-dir ./output

# Skip code parsing (use previously parsed ASTs)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-parse --output-dir ./output

# Only run Git ingestion and parsing (skip graph building)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-graph --output-dir ./output
```

### Advanced Configuration

```bash
# Configure resolution strategy based on codebase size
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy join --output-dir ./output  # Default, for repos with <2M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy hashmap --output-dir ./output  # For repos with 2-5M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy sharded --output-dir ./output  # For massive repos >5M definitions

# Configure Neo4j connection
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password --output-dir ./output

# Configure placeholder resolution
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --immediate-resolution --output-dir ./output
```

### Real-World Examples

```bash
# Index the FastAPI project
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/tiangolo/fastapi.git --output-dir ./fastapi_output

# Analyze local Python project with verbose output
python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_python_project --verbose --output-dir ./my_project_output

# Full indexing of a large JavaScript project with hashmap resolution
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/organization/large-js-project.git --full-indexing --resolution-strategy hashmap --output-dir ./js_project_output
```

## Documentation

- [Getting Started Guide](docs/getting_started.md): Quick setup and first steps with CodeIndexer
- [End-to-End Example](docs/end_to_end_example.md): Complete walkthrough with a real project
- [Ingestion Flow](docs/ingestion-flow.md): Detailed explanation of the ingestion pipeline
- [Placeholder Pattern](docs/placeholder_pattern.md): Information about the cross-file resolution approach
- [Graph Schema](docs/graph_schema.md): Neo4j graph database schema
- [Troubleshooting](docs/troubleshooting.md): Solutions for common issues and errors
- [Codebase Structure](docs/codebase_structure.md): Detailed overview of project organization

## Prerequisites

- Python 3.8+
- Neo4j (for graph storage)
- Git (for repository access)
- Tree-sitter (for code parsing)

## License

MIT