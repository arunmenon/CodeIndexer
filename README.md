# Code Indexer

A powerful code indexing and search system built with Google's Agent Development Kit (ADK).

## Overview

Code Indexer creates a semantic understanding of codebases by combining AST parsing, graph representation, and vector embeddings to enable natural language search and analysis of code.

## Features

- **Multi-Language Parsing**: Unified AST extraction across multiple programming languages
- **Code Knowledge Graph**: Graph-based representation of code structure and relationships
- **Vector Embeddings**: Semantic embedding of code chunks for similarity search
- **Natural Language Search**: Query code using natural language
- **Flexible Architecture**: Pluggable components with vector store abstraction

## Architecture

The system follows a multi-agent architecture using Google's ADK with these main components:

- **Git Ingestion**: Monitors repositories and extracts changed code
- **Code Parsing**: Extracts AST representations from code files
- **Graph Building**: Creates a knowledge graph of code entities and relationships
- **Chunking**: Divides code into semantic chunks for embedding
- **Embedding**: Generates vector representations of code chunks
- **Search**: Processes natural language queries and retrieves relevant code
- **Answer Composition**: Synthesizes search results into coherent answers

## Getting Started

### Prerequisites

- Python 3.8+
- Neo4j (for graph storage)
- Milvus or Qdrant (for vector storage)

### Installation

```bash
# Clone the repository
git clone https://github.com/arunmenon/CodeIndexer.git
cd CodeIndexer

# Install dependencies
pip install -r requirements.txt

# Start Milvus (optional)
docker-compose -f docker-compose.milvus.yml up -d
```

### Usage

```python
from code_indexer.api.search_api import CodeSearchAPI

# Initialize the search API
search_api = CodeSearchAPI(context)

# Search code
result = search_api.search("How does the authentication system work?")

# Get answer and code snippets
print(result["answer"])
for snippet in result["code_snippets"]:
    print(f"\n{snippet['entity_type']} {snippet['entity_id']} in {snippet['file_path']}:")
    print(snippet["code"])
```

## Documentation

- [Search Functionality](docs/search_functionality.md)
- [Milvus Integration](docs/milvus_integration.md)
- [Testing](docs/testing.md)

## Development

### Testing

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.