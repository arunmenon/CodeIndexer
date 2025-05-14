# CodeIndexer Ingestion Design Blueprint

This document outlines the design principles, architecture, and implementation details for the non-agentic ingestion pipeline of CodeIndexer. It serves as a reference for all future development of the ingestion layer.

## Core Architecture

The ingestion pipeline is structured as a sequence of stages:

1. **Git Ingestion**: Extract code from repositories
2. **Code Parsing**: Generate AST representations using Tree-sitter
3. **Graph Building**: Create a knowledge graph in Neo4j
4. **Chunking**: Divide code into semantic chunks
5. **Embedding**: Generate vector representations of code chunks

## Knowledge Graph Design

### Overall Graph Schema

The graph represents code as a network of interconnected entities:

| Node Type  | Description                                 | Key Properties                                      |
|------------|---------------------------------------------|-----------------------------------------------------|
| File       | Source code file                            | path, language, repo, commit                        |
| Class      | Class definition                            | name, start_line, end_line, docstring               |
| Function   | Function definition                         | name, start_line, end_line, params, docstring       |
| CallSite   | Location where a function is called         | target_name, line, col, resolved                    |
| ImportSite | Location where a module is imported         | import_name, alias, resolved                        |
| Import     | Imported module/package                     | name, module, member                                |

#### Relationship Types

| Type         | From       | To               | Properties           | Description                                         |
|--------------|------------|------------------|----------------------|-----------------------------------------------------|
| CONTAINS     | File       | Class/Function   | -                    | File contains the entity                            |
| CONTAINS     | Class      | Function         | -                    | Class contains the method                           |
| INHERITS_FROM| Class      | Class            | -                    | Class inheritance relationship                      |
| CALLS        | Function   | CallSite         | -                    | Function calls at this location                     |
| RESOLVES_TO  | CallSite   | Function         | -                    | Call resolves to this function definition           |
| IMPORTS      | File       | Import           | -                    | File imports this module                            |
| RESOLVES_TO  | ImportSite | Module/File      | -                    | Import resolves to this module                      |

### Enhanced Placeholder-Based Resolution (CRITICAL UPGRADE)

**Key Insight**: Maintain permanent placeholder nodes for calls and imports, with subsequent resolution phases, using Neo4j itself as the symbol table without external caching.

#### Placeholder Pattern Benefits:
- Complete call graph even with unresolved elements
- Preserves source location and context
- Robust to incremental updates
- Simpler query patterns
- Accurate dead code detection
- Supports dynamic resolution in dynamic languages
- No external caching service required

#### Resolution Approach Selection:

| Repository Size  | Recommended Approach | Memory Usage | Performance Characteristics |
|------------------|----------------------|--------------|----------------------------|
| ≤ 2M definitions | Pure Cypher Join     | Minimal      | ~30s for full repo resolution |
| 2-5M definitions | In-Process Hash Map  | ~25 bytes/def | ~5s for full repo resolution |
| >5M definitions  | Label-Sharded Index  | Minimal      | Scales linearly with unresolved placeholders |

#### Implementation Approach:

1. **During AST Processing (Phase 1)**:
   - Create CallSite nodes for every function call encountered
   - Link CallSite to containing Function with :CALLS relationship
   - Mark as unresolved (resolved=false)

2. **During Cross-File Resolution (Phase 2)**:
   - Match CallSite nodes to their target Function definitions
   - Create :RESOLVES_TO relationship
   - Update resolved=true but keep the original node

3. **Cypher Pattern for Resolution**:
```cypher
MATCH (c:CallSite {resolved:false})
MATCH (d:Function {name:c.target_name, repo:c.repo})
SET   c.resolved = true
MERGE (c)-[:RESOLVES_TO]->(d)
```

### Performance Considerations

- Expected storage impact: ~50 bytes per call site; ~400MB for 1M LOC repo
- Create indices on CallSite.target_name, CallSite.resolved, and CallSite.repo
- Use batched resolution for large repositories

## AST Extraction

### Tree-sitter Integration

Tree-sitter provides language-agnostic AST extraction:

#### Benefits:
- Support for 50+ languages
- Consistent AST structure across languages
- Error-tolerant parsing for malformed code
- Detailed syntax information
- Industry-standard parsing

#### Language Processing:
- Extensible language detection by file extension
- Fallback detection based on content patterns
- Standardized node representation

### Entity Extraction Process

Entity extraction is handled in three phases:

1. **Extraction**: Pull out classes, functions, imports from AST
2. **Node Creation**: Create individual entity nodes in Neo4j
3. **Resolution**: Link entities across files (using the placeholder pattern)

## Improvement Roadmap

### Phase 1: Core Placeholder-Based Resolution
- [ ] Implement CallSite & ImportSite nodes during AST traversal
- [ ] Implement resolution phase in graph building stage
- [ ] Add indices to support efficient resolution

### Phase 2: Enhanced Semantic Understanding
- [ ] Add type inference and tracking  
- [ ] Track variable usage and data flow
- [ ] Implement module-level dependency analysis

### Phase 3: Advanced Features
- [ ] Add historical tracking of code changes
- [ ] Implement semantic code chunk embedding tied to graph entities
- [ ] Create specialized indices for common query patterns

## Implementation Notes

### Tree-sitter Integration

Nodes should be normalized to a consistent format:
```python
{
    "type": node_type,
    "start_position": {"row": row, "column": col},
    "end_position": {"row": end_row, "column": end_col},
    "children": [...],
    "text": text  # for leaf nodes
}
```

### Placeholder Creation

During AST traversal:
```python
def extract_function_calls(ast_node, function_id, file_id):
    calls = find_entity_in_ast(ast_node, "Call")
    for call in calls:
        call_id = f"{file_id}:{call.start_line}:{call.start_col}"
        target_name = extract_call_target(call)
        
        # Create CallSite node
        neo4j_tool.execute_cypher("""
        MERGE (c:CallSite {id: $call_id})
        SET c.target_name = $target_name,
            c.line = $line,
            c.col = $col,
            c.resolved = false,
            c.repo = $repo
        WITH c
        MATCH (f:Function {id: $function_id})
        MERGE (f)-[:CALLS]->(c)
        """, {...})
```

### Resolution Phase

After all files are processed, use one of the following optimized approaches:

#### A. Pure Cypher Join (Simplest, For Repos ≤ 2M Definitions)

```python
def resolve_relationships(neo4j_tool, repository):
    # Resolve function calls in batches
    while True:
        result = neo4j_tool.execute_cypher("""
        MATCH (c:CallSite {repo: $repo, resolved: false})
        WITH c LIMIT 5000
        OPTIONAL MATCH (d {repo: $repo, symbol_fqn: c.target_name})
        FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END |
            SET c.resolved = true,
                c.target_fq = d.symbol_fqn
            CREATE (c)-[:RESOLVES_TO]->(d)
        )
        RETURN count(c) as processed
        """, {"repo": repository})
        
        processed_count = result[0]["processed"] if result else 0
        if processed_count == 0:
            break
```

#### B. In-Process Hash Map (For Larger Repos, 2-5M Definitions)

```python
def resolve_relationships(neo4j_tool, repository):
    # Build symbol map in memory
    symbol_map = {}
    symbol_result = neo4j_tool.execute_cypher("""
    MATCH (d {repo: $repo}) 
    WHERE exists(d.symbol_fqn)
    RETURN d.symbol_fqn AS name, id(d) AS node_id
    """, {"repo": repository})
    
    # Create lookup map
    for record in symbol_result:
        symbol_map[record["name"]] = record["node_id"]
    
    # Process in batches
    batch_size = 5000
    while True:
        batch = neo4j_tool.execute_cypher("""
        MATCH (c:CallSite {repo: $repo, resolved: false})
        RETURN id(c) AS call_id, c.target_name AS name 
        LIMIT $batch_size
        """, {"repo": repository, "batch_size": batch_size})
        
        if not batch:
            break
            
        # Process each call site in the batch
        for record in batch:
            target_name = record["name"]
            call_id = record["call_id"]
            
            if target_name in symbol_map:
                node_id = symbol_map[target_name]
                neo4j_tool.execute_cypher("""
                MATCH (c) WHERE id(c) = $call_id
                MATCH (d) WHERE id(d) = $node_id
                SET c.resolved = true, 
                    c.target_fq = d.symbol_fqn
                MERGE (c)-[:RESOLVES_TO]->(d)
                """, {"call_id": call_id, "node_id": node_id})
```

#### C. Label-Sharded Index (For Massive Repos > 5M Definitions)

During definition creation, create lightweight index nodes:
```python
def create_definition_with_index(neo4j_tool, def_props, def_type):
    # Create the definition node
    result = neo4j_tool.execute_cypher("""
    CREATE (d:%s $props)
    RETURN id(d) as node_id
    """ % def_type, {"props": def_props})
    
    node_id = result[0]["node_id"]
    
    # Create the index node
    neo4j_tool.execute_cypher("""
    MERGE (s:SymIndex {repo: $repo, name: $fqn})
    SET s.target_id = $node_id
    """, {
        "repo": def_props["repo"],
        "fqn": def_props["symbol_fqn"], 
        "node_id": node_id
    })
    
    return node_id
```

Resolution phase:
```python
def resolve_relationships(neo4j_tool, repository):
    # Resolve via the index nodes
    while True:
        result = neo4j_tool.execute_cypher("""
        MATCH (c:CallSite {repo: $repo, resolved: false})
        WITH c LIMIT 5000
        MATCH (s:SymIndex {repo: $repo, name: c.target_name})
        MATCH (d) WHERE id(d) = s.target_id
        SET c.resolved = true,
            c.target_fq = d.symbol_fqn
        MERGE (c)-[:RESOLVES_TO]->(d)
        RETURN count(c) as processed
        """, {"repo": repository})
        
        processed_count = result[0]["processed"] if result else 0
        if processed_count == 0:
            break
```

## Neo4j Optimization

### Recommended Indices

```cypher
CREATE INDEX file_repo_path IF NOT EXISTS FOR (f:File) ON (f.repository, f.path);
CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name, f.repository);
CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name, c.repository);
CREATE INDEX callsite_target IF NOT EXISTS FOR (c:CallSite) ON (c.target_name, c.repository, c.resolved);

# For resolver optimization
CREATE INDEX sym_by_repo_name IF NOT EXISTS FOR (d:Function|Class) ON (d.repo, d.symbol_fqn);

# For option C (label-sharded index)
CREATE INDEX sym_index IF NOT EXISTS FOR (s:SymIndex) ON (s.repo, s.name);
```

### Query Patterns for Common Operations

#### Find all calls to a function:
```cypher
MATCH (f:Function {name: "function_name", repository: "repo"})
MATCH (c:CallSite)-[:RESOLVES_TO]->(f)
RETURN c.line, c.file_path
```

#### Find dead code:
```cypher
MATCH (f:Function {repository: "repo"})
WHERE NOT (:CallSite)-[:RESOLVES_TO]->(f)
AND NOT f.name STARTS WITH "test_"
RETURN f.name, f.file_path
```

## Enhancement Planning

| Enhancement                                       | Priority | Complexity | Value |
|---------------------------------------------------|----------|------------|-------|
| Implement CallSite/ImportSite placeholders        | High     | Medium     | High  |
| Add optimized two-phase resolution                | High     | Medium     | High  |
| Implement composite Neo4j index for symbol lookup | High     | Low        | High  |
| Improve inheritance relationship tracking         | Medium   | Medium     | Medium|
| Add variable usage tracking                       | Medium   | High       | Medium|
| Implement module dependency analysis              | Medium   | Medium     | High  |
| Implement symbol map for large repos (option B)   | Medium   | Low        | High  |
| Add label-sharded index for massive repos (option C) | Low   | Medium     | Medium|
| Create time-series snapshots of graph changes     | Low      | High       | Medium|

## References

- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Neo4j Best Practices](https://neo4j.com/developer/guide-data-modeling/)
- [Knowledge Graph Design Patterns](https://patterns.knowledgegraphs.org/)