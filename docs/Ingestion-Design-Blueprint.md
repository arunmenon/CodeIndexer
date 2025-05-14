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

**Key Insight**: Maintain permanent placeholder nodes for calls and imports, with subsequent resolution phases.

#### Placeholder Pattern Benefits:
- Complete call graph even with unresolved elements
- Preserves source location and context
- Robust to incremental updates
- Simpler query patterns
- Accurate dead code detection
- Supports dynamic resolution in dynamic languages

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

After all files are processed:
```python
def resolve_relationships(neo4j_tool, repository):
    # Resolve function calls in batches
    while True:
        result = neo4j_tool.execute_cypher("""
        MATCH (c:CallSite {repo: $repo, resolved: false})
        WITH c LIMIT 5000
        MATCH (f:Function {name: c.target_name, repo: $repo})
        SET c.resolved = true
        MERGE (c)-[:RESOLVES_TO]->(f)
        RETURN count(*) as resolved
        """, {"repo": repository})
        
        resolved_count = result[0]["resolved"] if result else 0
        if resolved_count == 0:
            break
```

## Neo4j Optimization

### Recommended Indices

```cypher
CREATE INDEX file_repo_path IF NOT EXISTS FOR (f:File) ON (f.repository, f.path);
CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name, f.repository);
CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name, c.repository);
CREATE INDEX callsite_target IF NOT EXISTS FOR (c:CallSite) ON (c.target_name, c.repository, c.resolved);
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
| Add two-phase resolution                          | High     | Medium     | High  |
| Improve inheritance relationship tracking         | Medium   | Medium     | Medium|
| Add variable usage tracking                       | Medium   | High       | Medium|
| Implement module dependency analysis              | Medium   | Medium     | High  |
| Create time-series snapshots of graph changes     | Low      | High       | Medium|

## References

- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Neo4j Best Practices](https://neo4j.com/developer/guide-data-modeling/)
- [Knowledge Graph Design Patterns](https://patterns.knowledgegraphs.org/)