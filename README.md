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

# Process a repository
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo
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

## Usage

### Basic Commands

```bash
# Run full pipeline
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo

# Force full reindexing
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --full-indexing

# Skip specific stages
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-git --skip-parse
```

### Advanced Configuration

```bash
# Configure resolution strategy based on codebase size
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy join  # Default, for repos with <2M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy hashmap  # For repos with 2-5M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy sharded  # For massive repos >5M definitions
```

## Documentation

- [Getting Started Guide](docs/getting_started.md): Quick setup and first steps with CodeIndexer
- [End-to-End Example](docs/end_to_end_example.md): Complete walkthrough with a real project
- [Ingestion Flow](docs/ingestion-flow.md): Detailed explanation of the ingestion pipeline
- [Placeholder Pattern](docs/placeholder_pattern.md): Information about the cross-file resolution approach
- [Graph Schema](docs/graph_schema.md): Neo4j graph database schema
- [Troubleshooting](docs/troubleshooting.md): Solutions for common issues and errors

## Prerequisites

- Python 3.8+
- Neo4j (for graph storage)
- Git (for repository access)
- Tree-sitter (for code parsing)

## License

MIT