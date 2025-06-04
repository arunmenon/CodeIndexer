# CodeIndexer Documentation

Welcome to the CodeIndexer documentation. This index will help you navigate the available documentation resources.

## Getting Started

- [Getting Started Guide](getting_started.md): Quick setup instructions and your first indexing job
- [End-to-End Example](end_to_end_example.md): Complete walkthrough with a real Python project
- [Troubleshooting Guide](troubleshooting.md): Solutions for common issues and errors

## Core Concepts

- [Ingestion Flow](ingestion-flow.md): Detailed explanation of the ingestion pipeline
- [Graph Schema](graph_schema.md): Neo4j graph database schema and node types
- [Placeholder Pattern](placeholder_pattern.md): Cross-file relationship resolution technique

## Command Reference

### Basic Usage

```bash
# Run full pipeline on a repository
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo

# Force full reindexing (clears existing data)
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --full-indexing

# Skip specific stages
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-git --skip-graph
```

### Advanced Configuration

```bash
# Configure resolution strategy based on codebase size
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy join  # Default, for repos with <2M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy hashmap  # For repos with 2-5M definitions
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy sharded  # For massive repos >5M definitions

# Optimize performance
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --workers 8 --batch-size 1000
```

## Key Neo4j Queries

### Basic Exploration

```cypher
// Count each type of node
MATCH (f:File) RETURN count(f) as Files
MATCH (c:Class) RETURN count(c) as Classes
MATCH (f:Function) RETURN count(f) as Functions
```

### Finding Key Functions

```cypher
// Find the most called functions
MATCH (cs:CallSite)-[:RESOLVES_TO]->(f:Function)
RETURN f.name, count(cs) as callCount
ORDER BY callCount DESC
LIMIT 10
```

### Analyzing Dependencies

```cypher
// Find direct dependencies between files
MATCH (f1:File)-[:CONTAINS]->(:Function)<-[:RESOLVES_TO]-(:CallSite)<-[:CONTAINS]-(f2:File)
WHERE f1 <> f2
RETURN f1.path as source, f2.path as target, count(*) as strength
ORDER BY strength DESC
```

## Document Map

```
docs/
├── getting_started.md       # Installation and basic usage
├── end_to_end_example.md    # Complete walkthrough with real code
├── ingestion-flow.md        # Pipeline architecture and stages
├── graph_schema.md          # Neo4j schema and relationships
├── placeholder_pattern.md   # Cross-file resolution technique
├── troubleshooting.md       # Common issues and solutions
├── codebase_structure.md    # Project organization and modules
└── index.md                 # This document
```

## Further Resources

- [GitHub Repository](https://github.com/yourusername/CodeIndexer): Source code and issue tracking
- [Neo4j Documentation](https://neo4j.com/docs/): Documentation for the underlying graph database
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/): Information about the parsing library