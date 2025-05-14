# The Placeholder Pattern: Holistic Code Relationships

## Overview

The placeholder pattern implemented in CodeIndexer enables accurate cross-file relationship tracking in the knowledge graph. By creating explicit nodes for call sites and import sites, we can establish robust connections between code entities across file boundaries without requiring external caching services.

## Key Features

1. **Durable Placeholders**: Call sites and import sites are preserved as durable nodes in the graph, maintaining provenance information.
2. **Two-Phase Resolution**: Initial creation phase followed by efficient resolution phase.
3. **Optimized Performance**: Multiple resolution strategies for different codebase sizes.
4. **Confidence Scoring**: Resolution relationships include confidence scores for multi-match scenarios.

## Node Types

### CallSite Nodes

A CallSite node represents a location in code where a function or method is called. It captures:

- **Location**: File, line/column information
- **Context**: Containing function and/or class
- **Call Target**: Function name, optional module qualifier
- **Call Type**: Direct function call vs. attribute/method call

### ImportSite Nodes

An ImportSite node represents an import statement in code. It captures:

- **Location**: File, line information
- **Import Type**: Direct import vs. from-import
- **Import Details**: Module name, entity name, optional alias

## Resolution Strategies

The implementation offers three resolution strategies depending on codebase size:

### 1. Pure Cypher Join (Default)

Best for codebases with up to 2 million definitions.

```cypher
MATCH (cs:CallSite {call_name: "function_name"})
MATCH (f:Function {name: "function_name"})
WITH cs, f, 
     CASE WHEN f.file_id = cs.caller_file_id THEN 1.0 ELSE 0.7 END as score
ORDER BY score DESC
LIMIT 1
MERGE (cs)-[r:RESOLVES_TO]->(f)
SET r.score = score
```

### 2. In-Process Hash Map

Recommended for medium-sized codebases (2-5 million definitions):

1. Load all function/class definitions into memory once
2. Build in-memory indices for fast lookups
3. Process all CallSite nodes against the in-memory indices
4. Batch all resolutions back to Neo4j

### 3. Label-Sharded Index

Ideal for massive codebases (5+ million definitions):

1. Create specialized labels (FunctionA, FunctionB...) based on name prefixes
2. Use targeted queries that only search within relevant shards
3. Reduces the search space by orders of magnitude

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `create_placeholders` | Whether to create placeholder nodes | `True` |
| `immediate_resolution` | Resolve placeholders immediately during processing | `True` |
| `resolution_strategy` | Strategy to use: "join", "hashmap", or "sharded" | `"join"` |

## Usage Example

```python
from enhanced_graph_builder import EnhancedGraphBuilderRunner

# Configure the graph builder
config = {
    "neo4j_config": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password"
    },
    "create_placeholders": True,
    "immediate_resolution": True,
    "resolution_strategy": "join"
}

# Initialize the runner
runner = EnhancedGraphBuilderRunner(config)

# Run with parsed AST data
result = runner.run({
    "repository": "my-repo",
    "asts": ast_data,
    "is_full_indexing": False
})
```

## Key Benefits

1. **Accuracy**: More precise relationship tracking across files
2. **Provenance**: Maintains exact call location information 
3. **Incremental Updates**: Supports partial codebase updates
4. **Enhanced Queries**: Enables more sophisticated searches like:
   - "Find all callers of this function"
   - "Track dependency chains across modules"
   - "Identify dead code paths"

## Performance Considerations

The choice of resolution strategy has significant performance implications:

| Strategy | Repo Size | Memory Usage | Processing Time | Database Size |
|----------|-----------|--------------|-----------------|---------------|
| join | <2M defs | Low | Moderate | Smallest |
| hashmap | 2-5M defs | High | Fast | Medium |
| sharded | >5M defs | Medium | Moderate | Largest |

## Schema Optimizations

The implementation creates composite indices to accelerate resolution:

```cypher
CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.file_id);
CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.class_id);
CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name, c.file_id);
CREATE INDEX IF NOT EXISTS FOR (c:CallSite) ON (c.call_name, c.call_module);
```

## Advanced Query Examples

### Find all callers of a function
```cypher
MATCH (f:Function {name: "process_data"})
MATCH (cs:CallSite)-[:RESOLVES_TO]->(f)
RETURN cs
```

### Find which class methods call a specific function
```cypher
MATCH (f:Function {name: "validate_input"})
MATCH (cs:CallSite)-[:RESOLVES_TO]->(f)
MATCH (method:Function)-[:CONTAINS]->(cs)
MATCH (class:Class)-[:CONTAINS]->(method)
RETURN class.name, method.name, count(cs) as call_count
ORDER BY call_count DESC
```

### Track cross-module dependencies
```cypher
MATCH (f:File {path: "src/core/auth.py"})
MATCH (f)-[:CONTAINS]->(entity)
MATCH (cs:CallSite)-[:RESOLVES_TO]->(entity)
MATCH (caller_file:File)-[:CONTAINS*]->(cs)
WHERE caller_file.path <> f.path
RETURN DISTINCT caller_file.path
```

## Conclusion

The placeholder pattern creates a more comprehensive and accurate code graph by explicitly representing call sites and import sites as first-class nodes in the graph. This approach enables powerful queries, maintains code provenance, and supports incremental updates while still providing efficient performance through multiple resolution strategies.