# CodeIndexer Ingestion Flow

This document provides a comprehensive overview of the CodeIndexer ingestion pipeline, its architecture, and implementation details.

> **New to CodeIndexer?** Start with the [Getting Started Guide](./getting_started.md) first.
>
> **Want a practical example?** Check out the [End-to-End Example](./end_to_end_example.md).

## Architecture Overview

The ingestion pipeline follows a modular design with distinct stages that can be run independently or as part of an end-to-end process:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Git Ingestion  │────▶│  Code Parsing   │────▶│ Graph Building  │────▶│    Chunking     │────▶│    Embedding    │
│                 │     │                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Stage 1: Git Ingestion

Extracts code from repositories with incremental update support.

**Key Components:**
- Repository cloning/updating
- Change detection (full vs. incremental)
- File filtering
- Content extraction

**Implementation:**
- Uses GitTool class for Git operations
- Handles both remote and local repositories
- Maintains commit history for incremental updates
- Supports multiple repositories in a single run

### Stage 2: Code Parsing

Generates AST (Abstract Syntax Tree) representations using Tree-sitter.

**Key Components:**
- Language detection
- AST extraction
- Entity identification (functions, classes, etc.)
- Standard AST format generation

**Implementation:**
- Unified TreeSitterParser implementation
- Support for multiple languages (Python, JavaScript, TypeScript, Java)
- Error-tolerant parsing
- Parallel processing for large codebases

### Stage 3: Graph Building

Creates a knowledge graph in Neo4j with the placeholder pattern for cross-file resolution.

**Key Components:**
- Neo4j database integration
- Node and relationship creation
- Cross-file relationship resolution
- Incremental graph updates

**Implementation:**
- Uses the [placeholder pattern](./placeholder_pattern.md) for cross-file resolution
- Multiple resolution strategies based on codebase size
- Support for inheritance, call sites, and imports
- Optimization for large codebases

> For detailed information about the graph structure, see the [Graph Schema](./graph_schema.md) documentation.

### Stage 4: Chunking

Divides code into semantic chunks for embedding.

**Key Components:**
- Semantic chunking algorithms
- Contextual chunk boundaries
- Metadata preservation

### Stage 5: Embedding

Generates vector representations of code chunks for semantic search.

**Key Components:**
- Integration with embedding models
- Vector storage (Milvus)
- Indexing for similarity search

## Core Data Model

### Graph Schema

| Node Type   | Description                                 | Properties                                          |
|-------------|---------------------------------------------|-----------------------------------------------------|
| File        | Source code file                            | path, language, repo, commit                        |
| Class       | Class definition                            | name, start_line, end_line, docstring               |
| Function    | Function definition                         | name, start_line, end_line, params, docstring       |
| CallSite    | Location where a function is called         | target_name, line, col, resolved                    |
| ImportSite  | Location where a module is imported         | import_name, alias, resolved                        |
| Import      | Imported module/package                     | name, module, member                                |

### Relationships

| Type         | From       | To               | Properties                | Description                                   |
|--------------|------------|------------------|---------------------------|-----------------------------------------------|
| CONTAINS     | File       | Class/Function   | -                         | File contains the entity                      |
| CONTAINS     | Class      | Function         | -                         | Class contains the method                     |
| INHERITS_FROM| Class      | Class            | -                         | Class inheritance relationship                |
| CALLS        | Function   | CallSite         | -                         | Function calls at this location               |
| RESOLVES_TO  | CallSite   | Function         | score, timestamp          | Call resolves to this function definition     |
| IMPORTS      | File       | Import           | -                         | File imports this module                      |
| RESOLVES_TO  | ImportSite | Module/File      | score, timestamp          | Import resolves to this module                |

## Placeholder Pattern

The placeholder pattern is a key innovation that enables accurate cross-file relationship tracking:

1. **During AST Processing**:
   - Create CallSite nodes for function calls
   - Link to containing Function with :CALLS relationship
   - Mark as unresolved initially

2. **During Resolution Phase**:
   - Match CallSite nodes to target Function definitions
   - Create :RESOLVES_TO relationships
   - Update resolved status

3. **Resolution Strategies**:
   - **Join Strategy**: For codebases with <2M definitions
   - **HashMap Strategy**: For codebases with 2-5M definitions
   - **Sharded Strategy**: For massive codebases (>5M definitions)

## Running the Pipeline

### Basic Usage

```bash
# Run full pipeline on a repository
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo

# Full reindexing (clears existing data)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --full-indexing

# Skip specific stages
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-git --skip-graph
```

### Advanced Configuration

```bash
# Configure resolution strategy
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy join

# Control resolution timing
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --immediate-resolution
```

## Optimization Recommendations

### Neo4j Indices

```cypher
CREATE INDEX file_repo_path IF NOT EXISTS FOR (f:File) ON (f.repository, f.path);
CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name, f.repository);
CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name, c.repository);
CREATE INDEX callsite_target IF NOT EXISTS FOR (c:CallSite) ON (c.target_name, c.repository, c.resolved);
```

### Performance Tuning

| Codebase Size | Resolution Strategy | Neo4j Memory | Worker Processes |
|---------------|---------------------|--------------|------------------|
| Small (<100K LOC) | join            | 2-4GB        | 2-4              |
| Medium (100K-1M LOC) | join         | 4-8GB        | 4-8              |
| Large (1M-5M LOC) | hashmap         | 8-16GB       | 8-16             |
| Very Large (>5M LOC) | sharded      | 16-32GB      | 16-32            |

## Implementation Details

### Error Handling

The pipeline implements robust error handling:
- Graceful recovery from parsing errors
- Fallback to full indexing when incremental fails
- Detailed error logging and reporting

### Incremental Updates

For efficient incremental updates:
- Maintains commit history for each repository
- Only processes changed files
- Supports partial graph updates
- Preserves existing relationships

## Conclusion

The CodeIndexer ingestion pipeline provides a robust, scalable solution for code analysis and knowledge graph creation. Its modular design allows for flexible deployment and optimization for different codebase sizes and use cases.

## Next Steps

- See the [End-to-End Example](./end_to_end_example.md) for a practical demonstration
- Explore the [Graph Schema](./graph_schema.md) to understand the resulting knowledge graph
- Learn about the [Placeholder Pattern](./placeholder_pattern.md) for detailed cross-file resolution information