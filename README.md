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

Our CLI provides an intuitive interface with rich help text and progress tracking. To see all available options:

```bash
python -m code_indexer.ingestion.cli.run_pipeline --help
```

<details>
<summary>📋 CLI Help Output (click to expand)</summary>

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                              CODE INDEXER CLI                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

A powerful tool for code analysis that extracts semantic information from 
repositories and builds a queryable knowledge graph.

This pipeline follows three main stages:
  1. 📦 Git Ingestion:    Extract files and metadata from repositories
  2. 🔍 Code Parsing:     Generate Abstract Syntax Trees (ASTs) from source code
  3. 🔄 Graph Building:   Create a knowledge graph with code relationships

📌 Required Arguments:
  --repo-path PATH_OR_URL
                        Path to local repository or URL of remote repository
                        (GitHub, GitLab, etc.)

🔧 Basic Options:
  --output-dir DIR      Directory to store outputs (default: ./output/<repo_name>)
  --branch BRANCH       Git branch to process (default: main)
  --commit COMMIT_HASH  Git commit to process (default: HEAD)
  --verbose             Enable verbose logging with detailed debug information

🔄 Processing Options:
  --full-indexing       Perform full indexing (clear existing data and reindex everything)
  --skip-git            Skip git ingestion step (use previous results from output directory)
  --skip-parse          Skip code parsing step (use previous results from output directory)
  --skip-graph          Skip graph building step (stop after parsing)

⚙️ Advanced Options:
  --resolution-strategy STRATEGY
                        Strategy for cross-file reference resolution:
                        join - Standard SQL-like joins (default, best for small/medium repos)
                        hashmap - In-memory hashmap (faster for medium repos)
                        sharded - Distributed resolution (best for very large repos)
  --immediate-resolution
                        Resolve placeholders immediately rather than in bulk
                        (slower but lower memory usage)

🔐 Git Authentication:
  --ssh-auth            Use SSH authentication for Git operations (required for many private repositories)
  --ssh-key KEY_PATH    Path to SSH private key for Git authentication (default: uses SSH agent or
                        CODEINDEXER_SSH_KEY env var)

🔌 Neo4j Connection:
  --neo4j-uri URI       Neo4j URI (default: from env var NEO4J_URI or bolt://localhost:7687)
  --neo4j-user USER     Neo4j username (default: from env var NEO4J_USER or neo4j)
  --neo4j-password PASSWORD
                        Neo4j password (default: from env var NEO4J_PASSWORD or password)
```

</details>

### Basic Commands

```bash
# Index a local repository (output dir automatically created based on repo name)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/local/repo

# Index a remote repository (GitHub, GitLab, etc.)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/repo.git

# Use SSH authentication for private repositories
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/private-repo.git --ssh-auth

# Use SSH authentication with a specific SSH key
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/private-repo.git --ssh-auth --ssh-key ~/.ssh/id_rsa

# Specify branch (default is 'main')
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/username/repo.git --branch develop

# Force full reindexing (instead of incremental)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --full-indexing

# Enable verbose logging
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --verbose
```

### Selective Processing

```bash
# Skip Git ingestion (use previously ingested files)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-git

# Skip code parsing (use previously parsed ASTs)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-parse

# Only run Git ingestion and parsing (skip graph building)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-graph
```

### Advanced Configuration

```bash
# Configure resolution strategy based on codebase size
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy join  # Default, for repos with <2M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy hashmap  # For repos with 2-5M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy sharded  # For massive repos >5M definitions

# Configure Neo4j connection
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password

# Configure placeholder resolution
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --immediate-resolution
```

### Real-World Examples

```bash
# Index the FastAPI project
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/tiangolo/fastapi.git

# Analyze local Python project with verbose output
python -m code_indexer.ingestion.cli.run_pipeline --repo-path ./my_python_project --verbose

# Full indexing of a large JavaScript project with hashmap resolution
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.com/organization/large-js-project.git --full-indexing --resolution-strategy hashmap

# Access a private enterprise GitHub repository with SSH authentication
python -m code_indexer.ingestion.cli.run_pipeline --repo-path https://github.enterprise.com/internal/private-repo.git --ssh-auth --branch develop
```

### CLI Output Example

<details>
<summary>📋 Sample CLI Output (click to expand)</summary>

```
═════════════════════════════════════════════════════════════════════════════
                          ℹ️  CodeIndexer Pipeline                          
═════════════════════════════════════════════════════════════════════════════

📦 Repository: /path/to/my_project
📂 Output Directory: ./output/my_project
🔖 Branch: main
🔒 Commit: HEAD

────────────────────────────────────────────────────────────────────────────
PIPELINE STATUS
  1. Git Ingestion: ⏳ PENDING
  2. Code Parsing: ⏳ PENDING
  3. Graph Building: ⏳ PENDING
────────────────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────────────────
STAGE 1/3: 📦 GIT INGESTION
────────────────────────────────────────────────────────────────────────────
📂 Processing repository: /path/to/my_project
📊 Extracted 1,245 files in 3.2 seconds

────────────────────────────────────────────────────────────────────────────
STAGE 2/3: 🔍 CODE PARSING
────────────────────────────────────────────────────────────────────────────
🔍 Parsing 1,245 files...
📊 Generated 1,203 ASTs in 8.5 seconds
⚡ Processing rate: 146.5 files/second

────────────────────────────────────────────────────────────────────────────
STAGE 3/3: 🔄 GRAPH BUILDING
────────────────────────────────────────────────────────────────────────────
🔄 Building knowledge graph from 1,203 ASTs...
🔍 Using join resolution strategy
📊 Created 15,678 nodes and 32,456 relationships
📞 Resolved 2,134 of 2,567 call sites (83.1%)

────────────────────────────────────────────────────────────────────────────
FINAL PIPELINE STATUS
  1. Git Ingestion: ✅ DONE (3.2 seconds)
  2. Code Parsing: ✅ DONE (8.5 seconds)
  3. Graph Building: ✅ DONE (12.3 seconds)
────────────────────────────────────────────────────────────────────────────

═════════════════════════════════════════════════════════════════════════════
               ✅ SUCCESS: KNOWLEDGE GRAPH GENERATION COMPLETED in 12.3 seconds
═════════════════════════════════════════════════════════════════════════════

📊 REPOSITORY SUMMARY
  📦 Repository: my_project
  🔖 Branch: main
  🔒 Commit: HEAD

📈 PROCESSING STATISTICS
  📄 Files Processed: 1,203

🔄 GRAPH STATISTICS
  📍 Nodes Created: 15,678
  🔗 Relationships Created: 32,456
  📞 Call Sites: 2,567
  ✓ Resolved Calls: 2,134 (83.1%)
  📦 Imported Modules: 347

💾 RESULTS LOCATION
  📁 Output Directory: /Users/username/projects/CodeIndexer/output/my_project
  📄 Graph Output: /Users/username/projects/CodeIndexer/output/my_project/graph_output.json

⏩ NEXT STEPS
  • Query the knowledge graph using Neo4j Browser at http://localhost:7474/
  • Run semantic search on the code using the search API
  • Visualize code relationships with the graph explorer

⏱️ Total pipeline execution time: 24.0 seconds

═════════════════════════════════════════════════════════════════════════════
                   ✅ SUCCESS: Pipeline completed successfully               
═════════════════════════════════════════════════════════════════════════════
```

</details>

## Documentation

- [Getting Started Guide](docs/getting_started.md): Quick setup and first steps with CodeIndexer
- [End-to-End Example](docs/end_to_end_example.md): Complete walkthrough with a real project
- [Ingestion Flow](docs/ingestion-flow.md): Detailed explanation of the ingestion pipeline
- [SSH Authentication](docs/ssh_authentication.md): Guide for accessing private repositories
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