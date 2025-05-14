# Code Indexer

A powerful code indexing and search system with modular architecture.

## Overview

Code Indexer creates a semantic understanding of codebases by combining AST parsing, graph representation, and vector embeddings to enable natural language search and analysis of code.

## Features

- **Multi-Language Parsing**: Universal AST extraction using Tree-sitter for 50+ languages
- **Code Knowledge Graph**: Graph-based representation of code structure and relationships
- **Vector Embeddings**: Semantic embedding of code chunks for similarity search
- **Natural Language Search**: Query code using natural language
- **Flexible Architecture**: Two-tier design with independent ingestion and semantic layers
- **Cross-File Resolution**: Accurate tracking of call sites and import relationships

## Architecture

The system follows a two-tier architecture:

### Stage 1: Ingestion Pipeline (Non-Agentic)
- **Git Ingestion**: Extracts code from repositories
- **Code Parsing**: Generates AST representations using Tree-sitter
- **Graph Building**: Creates a knowledge graph in Neo4j
  - **Placeholder Pattern**: Tracks call sites and import sites as first-class nodes
  - **Cross-File Resolution**: Creates accurate relationships across file boundaries
- **Chunking**: Divides code into semantic chunks
- **Embedding**: Generates vector representations of code chunks

### Stage 2: Semantic Layer (ADK-Based)
- **Query Processing**: Understands natural language queries
- **Vector Search**: Retrieves relevant code chunks
- **Graph Search**: Finds related code structures and relationships
- **Answer Composition**: Synthesizes search results into coherent answers

## Getting Started

### Prerequisites

- Python 3.8+
- Neo4j (for graph storage)
- Milvus or Qdrant (for vector storage)

### Installation

#### Basic Installation (Ingestion Only)

```bash
# Clone the repository
git clone https://github.com/arunmenon/CodeIndexer.git
cd CodeIndexer

# Install base package
pip install -e .

# Start Neo4j and Milvus (optional)
docker-compose up -d neo4j milvus
```

#### Full Installation (with Semantic Layer)

```bash
# Install with semantic features
pip install -e ".[semantic,vector]"
```

### Setup Tree-sitter

The ingestion pipeline uses Tree-sitter for robust, language-agnostic code parsing:

```bash
# Set up Tree-sitter language parsers (recommended languages)
python -m code_indexer.ingestion.setup_tree_sitter

# Or set up specific languages
python -m code_indexer.ingestion.setup_tree_sitter --languages python,javascript,typescript,java
```

## Usage

### Running the Ingestion Pipeline

```bash
# Process a repository
codeindexer-ingest --repo https://github.com/example/repo --output-dir ./results

# Run incremental indexing
codeindexer-ingest --repo https://github.com/example/repo --mode incremental

# Full reindexing
codeindexer-ingest --repo https://github.com/example/repo --mode full

# Run specific stage
codeindexer-ingest --repo https://github.com/example/repo --step graph

# Detect dead code during ingestion
codeindexer-ingest --repo https://github.com/example/repo --detect-dead-code
```

### Running the Enhanced Graph Builder

```bash
# Process a repository with enhanced graph builder (placeholder pattern)
python run_enhanced_graph_builder.py --repo-path /path/to/repo --resolution-strategy join

# Options for different codebase sizes
python run_enhanced_graph_builder.py --repo-path /path/to/repo --resolution-strategy hashmap  # For medium repos (2-5M definitions)
python run_enhanced_graph_builder.py --repo-path /path/to/repo --resolution-strategy sharded  # For large repos (>5M definitions)

# Control how resolution happens
python run_enhanced_graph_builder.py --repo-path /path/to/repo --immediate-resolution  # Resolve during processing
python run_enhanced_graph_builder.py --repo-path /path/to/repo  # Bulk resolution at the end
```

### Running the Semantic API (requires ADK)

```bash
# Start the semantic API
codeindexer-semantic --team code_indexer/semantic/teams/query_team.yaml --port 8000
```

## Docker

```bash
# Build base image (ingestion only)
docker build -t codeindexer:latest .

# Build with semantic features
docker build -t codeindexer:semantic --target semantic .

# Run container
docker run -p 8000:8000 codeindexer:semantic
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"
```

## Advanced Graph Features

The enhanced graph builder implements the placeholder pattern for accurate cross-file relationship tracking:

- **Durable Placeholders**: Call sites and import sites preserved as first-class nodes
- **Two-Phase Resolution**: Efficient resolution of placeholders to their targets
- **Multiple Resolution Strategies**: Options for different codebase sizes
  - Pure Cypher Join: Best for repos with <2M definitions
  - In-Process Hash Map: Optimized for 2-5M definitions
  - Label-Sharded Index: For massive codebases (>5M definitions)
- **Relationship Confidence**: Scores indicate certainty of resolutions

Read more about the placeholder pattern in [docs/placeholder_pattern.md](docs/placeholder_pattern.md).

## License

MIT