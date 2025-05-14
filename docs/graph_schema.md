# Code Knowledge Graph Schema

## Overview

The Code Knowledge Graph represents code structure, relationships, and semantics in a Neo4j graph database. The schema includes nodes for code entities (files, classes, functions) as well as placeholders for cross-file relationships (call sites, import sites).

## Node Types

### Core Entities

| Node Label | Description | Key Properties |
|------------|-------------|----------------|
| `File` | Source code file | `id`, `path`, `language`, `repository` |
| `Class` | Class definition | `id`, `name`, `start_line`, `end_line`, `docstring` |
| `Function` | Function or method definition | `id`, `name`, `start_line`, `end_line`, `params`, `is_method`, `docstring` |
| `Import` | Imported module or entity | `name`, `module`, `alias` |

### Placeholder Nodes

| Node Label | Description | Key Properties |
|------------|-------------|----------------|
| `CallSite` | Location where a function/method is called | `id`, `call_name`, `call_module`, `start_line`, `end_line`, `is_attribute_call` |
| `ImportSite` | Location of an import statement | `id`, `import_name`, `module_name`, `alias`, `is_from_import` |

## Relationship Types

### Structural Relationships

| Relationship Type | Source | Target | Description | Properties |
|-----------------|--------|--------|-------------|------------|
| `CONTAINS` | `File` | `Class`, `Function`, `CallSite`, `ImportSite` | Entity containment | N/A |
| `CONTAINS` | `Class` | `Function`, `CallSite` | Method/call containment | N/A |
| `CONTAINS` | `Function` | `CallSite` | Call within function body | N/A |

### Semantic Relationships

| Relationship Type | Source | Target | Description | Properties |
|-----------------|--------|--------|-------------|------------|
| `INHERITS_FROM` | `Class` | `Class` | Class inheritance | N/A |
| `IMPORTS` | `File` | `Import` | File imports module/entity | N/A |
| `CALLS` | `File`, `Function` | `Function` | Function call | `line_numbers` |
| `RESOLVES_TO` | `CallSite` | `Function` | Call site resolution | `score`, `timestamp` |
| `RESOLVES_TO` | `ImportSite` | `Class`, `Function` | Import site resolution | `score`, `timestamp` |

## Additional Properties

### File Node

```
File {
    id: String,                 // Unique identifier
    path: String,               // File path within repo
    name: String,               // Filename
    language: String,           // Programming language
    repository: String,         // Repository name
    repository_url: String,     // Repository URL
    commit: String,             // Commit hash
    branch: String,             // Branch name
    created_at: DateTime,       // Creation timestamp
    last_updated: DateTime      // Last update timestamp
}
```

### Class Node

```
Class {
    id: String,                 // Unique identifier
    name: String,               // Class name
    docstring: String,          // Documentation string
    start_line: Integer,        // Starting line number
    end_line: Integer,          // Ending line number
    file_id: String,            // Reference to containing file
    parents: [String],          // List of parent class names
    created_at: DateTime,       // Creation timestamp
    last_updated: DateTime      // Last update timestamp
}
```

### Function Node

```
Function {
    id: String,                 // Unique identifier
    name: String,               // Function name
    docstring: String,          // Documentation string
    start_line: Integer,        // Starting line number
    end_line: Integer,          // Ending line number
    params: [String],           // Parameter names
    return_type: String,        // Return type
    file_id: String,            // Reference to containing file
    class_id: String,           // Reference to containing class (if method)
    is_method: Boolean,         // Whether this is a class method
    created_at: DateTime,       // Creation timestamp
    last_updated: DateTime      // Last update timestamp
}
```

### CallSite Node

```
CallSite {
    id: String,                 // Unique identifier
    caller_file_id: String,     // ID of file containing the call site
    caller_function_id: String, // ID of function containing the call site
    caller_class_id: String,    // ID of class containing the call site
    call_name: String,          // Name of function/method being called
    call_module: String,        // Module qualifier for the call
    start_line: Integer,        // Starting line number
    start_col: Integer,         // Starting column number
    end_line: Integer,          // Ending line number
    end_col: Integer,           // Ending column number
    is_attribute_call: Boolean, // Whether this is an attribute call (obj.method())
    created_at: DateTime,       // Creation timestamp
    last_updated: DateTime      // Last update timestamp
}
```

### ImportSite Node

```
ImportSite {
    id: String,                 // Unique identifier
    file_id: String,            // ID of file containing the import site
    import_name: String,        // Name of imported entity
    module_name: String,        // Name of module being imported from
    alias: String,              // Alias used for the import
    is_from_import: Boolean,    // Whether this is a from-import statement
    start_line: Integer,        // Starting line number
    end_line: Integer,          // Ending line number
    created_at: DateTime,       // Creation timestamp
    last_updated: DateTime      // Last update timestamp
}
```

## Indexes and Constraints

```cypher
// Unique constraints
CREATE CONSTRAINT IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:CallSite) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:ImportSite) REQUIRE n.id IS UNIQUE;

// Lookup indexes
CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path);
CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.repository);
CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name);
CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name);

// Composite indexes for efficient resolution
CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.file_id);
CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.class_id);
CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name, c.file_id);
CREATE INDEX IF NOT EXISTS FOR (c:CallSite) ON (c.call_name, c.call_module);
CREATE INDEX IF NOT EXISTS FOR (i:ImportSite) ON (i.import_name, i.module_name);
```

## Sample Queries

### Getting all calls to a specific function

```cypher
MATCH (f:Function {name: "process_data"})
MATCH (cs:CallSite)-[:RESOLVES_TO]->(f)
OPTIONAL MATCH (caller_func:Function)-[:CONTAINS]->(cs)
RETURN cs.start_line, cs.end_line, caller_func.name
```

### Finding dead code (functions with no callers)

```cypher
MATCH (f:Function)
WHERE NOT EXISTS {
  MATCH (cs:CallSite)-[:RESOLVES_TO]->(f)
}
RETURN f.name, f.file_id
```

### Tracking cross-file dependencies

```cypher
MATCH (f:File {path: "src/core/auth.py"})
MATCH (f)-[:CONTAINS]->(entity)
MATCH (cs:CallSite)-[:RESOLVES_TO]->(entity)
MATCH (caller_file:File)-[:CONTAINS*]->(cs)
WHERE caller_file.path <> f.path
RETURN DISTINCT caller_file.path
```

### Finding class hierarchy

```cypher
MATCH (c:Class {name: "BaseController"})
MATCH path = (subclass:Class)-[:INHERITS_FROM*]->(c)
RETURN path
```