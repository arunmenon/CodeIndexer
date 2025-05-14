# CodeIndexer Ingestion Pipeline (Stage 1)

This package provides a standalone, non-agentic implementation for code ingestion:

1. **Git Repository Handling**: Clones and extracts code from git repositories
2. **AST Extraction**: Parses code files into Abstract Syntax Trees (ASTs)
3. **Graph Integration**: Builds a graph representation in Neo4j

## Architecture

The ingestion pipeline represents Stage 1 of the CodeIndexer system - creating a foundational code structure representation without requiring LLM intelligence or ADK dependencies. It is designed to be:

- **Fast & Efficient**: Optimized for processing large codebases
- **Non-Agentic**: No dependencies on LLM or ADK components
- **Standalone**: Can run independently of the semantic layer
- **Deterministic**: Produces consistent results with the same inputs

## Components

### DirectGitIngestionRunner
Handles repository cloning and file extraction, with support for:
- Full or incremental indexing
- File filtering by type and size
- Commit history tracking
- Batch processing

### DirectCodeParserRunner
Parses code files into Abstract Syntax Trees (ASTs), with support for:
- Multiple programming languages via Tree-sitter
- Universal parsing for 50+ languages
- Consistent AST structure across languages
- Error-tolerant parsing for malformed code
- Detailed syntax and semantic information
- Code structure extraction
- Metadata attachment

### DirectGraphBuilderRunner
Builds a graph representation in Neo4j, with support for:
- Code entity extraction (files, classes, functions)
- Relationship mapping
- Schema management
- Transaction handling

### DirectNeo4jTool
Provides a direct interface to Neo4j operations without ADK dependencies.

## Setup

### Tree-sitter Installation

This pipeline uses Tree-sitter for robust, language-agnostic code parsing. To set up the necessary language parsers:

```bash
# Install dependencies
pip install -r ingestion_pipeline/requirements.txt

# Set up Tree-sitter language parsers (recommended languages)
./ingestion_pipeline/setup_tree_sitter.py

# Or set up specific languages
./ingestion_pipeline/setup_tree_sitter.py --languages python,javascript,typescript,java

# Or set up all supported languages
./ingestion_pipeline/setup_tree_sitter.py --all
```

## Usage

Run the entire pipeline with:

```bash
./run_ingestion.py --repo https://github.com/example/repo --output-dir ./results
```

Or run individual stages:

```bash
# Git ingestion only
./run_ingestion.py --repo https://github.com/example/repo --step git

# Code parsing only (requires git output)
./run_ingestion.py --step parse --output-dir ./results

# Graph building only (requires parser output)
./run_ingestion.py --step graph --neo4j-uri bolt://localhost:7687
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--repo` | Repository URL to ingest | Required |
| `--branch` | Branch to process | `main` |
| `--output-dir` | Directory to save results | Current directory |
| `--mode` | Processing mode (incremental/full) | `incremental` |
| `--force-reindex` | Force reindexing | `false` |
| `--neo4j-uri` | Neo4j URI | `bolt://localhost:7687` |
| `--neo4j-user` | Neo4j username | `neo4j` |
| `--neo4j-password` | Neo4j password | `password` |
| `--step` | Run specific step (git/parse/graph/all) | `all` |

## Integration with Stage 2 (Semantic Layer)

This pipeline creates a foundation that can be enriched by a semantic layer in Stage 2. The output files from this pipeline serve as input for semantic analysis agents that can:

- Identify design patterns and architectural styles
- Generate documentation
- Detect code quality issues
- Provide semantic search capabilities
- Create higher-level abstractions

The separation between Stage 1 (Ingestion) and Stage 2 (Semantic Analysis) allows for:
- Better performance for routine updates
- Flexibility in choosing LLM providers for semantic analysis
- Independent scaling of ingestion and analysis processes