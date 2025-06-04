# Code Knowledge Graph Schema

## Overview

The Code Knowledge Graph represents code structure, relationships, and semantics in a Neo4j graph database. The schema includes nodes for code entities (files, classes, functions) as well as placeholders for cross-file relationships (call sites, import sites).

> **New to CodeIndexer?** Start with the [Getting Started Guide](./getting_started.md).
>
> **Want to understand how this graph is created?** See the [Ingestion Flow](./ingestion-flow.md) documentation.
>
> **Looking for practical examples?** Check the [End-to-End Example](./end_to_end_example.md).

## Graph Structure Visualization

```
                           ┌───────────┐
                           │   File    │
                           └───┬───────┘
                               │
                               │ CONTAINS
                               ▼
       ┌───────────────┬───────────────┬───────────────┐
       │               │               │               │
       ▼               ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│   Class    │  │  Function  │  │ ImportSite │  │  CallSite  │
└──────┬─────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
       │              │               │               │
       │ CONTAINS     │ CONTAINS      │ RESOLVES_TO   │ RESOLVES_TO
       ▼              ▼               │               │
┌────────────┐  ┌────────────┐        │               │
│  Function  │  │  CallSite  │        │               │
└─────┬──────┘  └────────────┘        │               │
       │                              │               │
       │ INHERITS_FROM                ▼               ▼
       │                        ┌────────────┐  ┌────────────┐
       └─────────────────────► │   Import   │  │  Function  │
                               └────────────┘  └────────────┘
```

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

## Real-World Examples

### Example 1: Simple Function Call

**Python Code:**
```python
# file: math_utils.py
def add(a, b):
    return a + b

# file: calculator.py
from math_utils import add

def calculate_sum(x, y):
    return add(x, y)
```

**Graph Representation:**
```
(File:math_utils.py) -CONTAINS-> (Function:add)
(File:calculator.py) -CONTAINS-> (Function:calculate_sum)
(File:calculator.py) -CONTAINS-> (ImportSite:math_utils.add)
(File:calculator.py) -CONTAINS-> (CallSite:add)
(Function:calculate_sum) -CONTAINS-> (CallSite:add)
(ImportSite:math_utils.add) -RESOLVES_TO-> (Function:add)
(CallSite:add) -RESOLVES_TO-> (Function:add)
```

**Visualization:**
```
┌────────────────────┐           ┌────────────────────┐
│  File:math_utils.py│           │ File:calculator.py │
└──────────┬─────────┘           └──────────┬─────────┘
           │                                │
           │ CONTAINS                       │ CONTAINS
           ▼                                ▼
┌────────────────────┐      ┌─────────────────────────────┐
│   Function:add     │      │    Function:calculate_sum   │
└────────────────────┘      └───────────────┬─────────────┘
           ▲                                │
           │                                │ CONTAINS
           │                                ▼
           │                      ┌────────────────────┐
           │                      │   CallSite:add     │
           │                      └──────────┬─────────┘
           │                                 │
           └─────────────────────────────────┘
                      RESOLVES_TO
```

### Example 2: Class Inheritance with Method Calls

**Python Code:**
```python
# file: base.py
class Animal:
    def speak(self):
        pass

# file: dog.py
from base import Animal

class Dog(Animal):
    def speak(self):
        return "Woof!"
    
    def bark(self):
        return self.speak()

# file: main.py
from dog import Dog

def create_dog():
    dog = Dog()
    sound = dog.speak()
    return sound
```

**Graph Representation (simplified):**
```
(File:base.py) -CONTAINS-> (Class:Animal)
(Class:Animal) -CONTAINS-> (Function:speak)

(File:dog.py) -CONTAINS-> (Class:Dog)
(Class:Dog) -INHERITS_FROM-> (Class:Animal)
(Class:Dog) -CONTAINS-> (Function:speak)
(Class:Dog) -CONTAINS-> (Function:bark)
(Function:bark) -CONTAINS-> (CallSite:speak)
(CallSite:speak) -RESOLVES_TO-> (Function:speak)

(File:main.py) -CONTAINS-> (Function:create_dog)
(Function:create_dog) -CONTAINS-> (CallSite:Dog)
(Function:create_dog) -CONTAINS-> (CallSite:speak)
(CallSite:Dog) -RESOLVES_TO-> (Class:Dog)
(CallSite:speak) -RESOLVES_TO-> (Function:speak)
```

**Visualization of Class Hierarchy:**
```
┌────────────┐
│ Class:Animal│
└──────┬─────┘
       │
       │ INHERITS_FROM
       │
       ▼
┌────────────┐
│ Class:Dog  │
└────────────┘
```

## Function Call Resolution Flow

When a function call is detected in the code, it goes through the following resolution process:

```
┌───────────┐     ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  Parse    │────►│ Create        │────►│ Create        │────►│ Resolve       │
│  AST      │     │ Function Node │     │ CallSite Node │     │ Relationships │
└───────────┘     └───────────────┘     └───────────────┘     └───────────────┘
                                                                     │
                                                                     ▼
┌────────────────────┐     ┌───────────────┐     ┌───────────────┐
│ Update Score       │◄────│ Handle        │◄────│ Find Matching │
│ & Timestamp        │     │ Ambiguity     │     │ Function      │
└────────────────────┘     └───────────────┘     └───────────────┘
```

For a detailed explanation of how this resolution works, see the [Placeholder Pattern](./placeholder_pattern.md) documentation.

## Cross-File Resolution Example

Consider a real-world Python project with multiple files:

**models.py**:
```python
class User:
    def __init__(self, username):
        self.username = username
    
    def validate(self):
        return len(self.username) > 3
```

**services.py**:
```python
from models import User
from utils import format_username

def create_user(raw_username):
    formatted_name = format_username(raw_username)
    user = User(formatted_name)
    if user.validate():
        return user
    return None
```

**utils.py**:
```python
def format_username(username):
    return username.strip().lower()
```

**Graph Data Model Visualization:**
```
┌───────────────┐           ┌───────────────┐            ┌───────────────┐
│ File:models.py│           │File:services.py│           │ File:utils.py │
└───────┬───────┘           └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Class:User  │           │    Function:  │           │   Function:   │
└───────┬───────┘           │  create_user  │           │format_username│
        │                   └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        ▼                           │                           │
┌───────────────┐                   │                           │
│   Function:   │◄──────────────────┘                           │
│   validate    │        RESOLVES_TO                            │
└───────────────┘                                               │
        ▲                                                       │
        │                                                       │
        │                   ┌───────────────┐                   │
        └───────────────────┤  CallSite:    │                   │
              RESOLVES_TO   │   validate    │                   │
                            └───────────────┘                   │
                                                                │
                            ┌───────────────┐                   │
                            │  CallSite:    │                   │
                            │format_username│◄──────────────────┘
                            └───────────────┘      RESOLVES_TO
```

## Node Properties Details

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

## Placeholder Pattern Implementation Flow

The placeholder pattern resolves cross-file dependencies in two phases:

```
Phase 1: Creation
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Parse Code      │────►│ Create Entity   │────►│ Create          │
│ and AST         │     │ Nodes           │     │ Placeholder     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │ Link to         │
                                              │ Containing      │
                                              │ Entities        │
                                              └─────────────────┘
Phase 2: Resolution
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Query for       │────►│ Match Target    │────►│ Create          │
│ Unresolved      │     │ Entities        │     │ RESOLVES_TO     │
│ Placeholders    │     │                 │     │ Relationships   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │ Calculate       │
                                              │ Confidence      │
                                              │ Score           │
                                              └─────────────────┘
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

## Sample Queries and Visualizations

### Getting all calls to a specific function

```cypher
MATCH (f:Function {name: "process_data"})
MATCH (cs:CallSite)-[:RESOLVES_TO]->(f)
OPTIONAL MATCH (caller_func:Function)-[:CONTAINS]->(cs)
RETURN cs.start_line, cs.end_line, caller_func.name
```

**Visual Result Example:**
```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│ Function:   │◄────────│ CallSite at │◄────────│ Function:   │
│ process_data│         │ line 42     │         │ handle_data │
└─────────────┘         └─────────────┘         └─────────────┘
      ▲                                                ▲
      │                                                │
      │                 ┌─────────────┐                │
      └─────────────────┤ CallSite at │◄───────────────┘
                        │ line 87     │
                        └─────────────┘
```

### Finding dead code (functions with no callers)

```cypher
MATCH (f:Function)
WHERE NOT EXISTS {
  MATCH (cs:CallSite)-[:RESOLVES_TO]->(f)
}
RETURN f.name, f.file_id
```

**Visual Example:**
```
┌────────────────┐
│ File:utils.py  │
└────────┬───────┘
         │
         │ CONTAINS
         ▼
┌────────────────┐   ┌───────────────┐
│Function:       │   │ No CallSites  │
│unused_function │◄──┤ point to this │
└────────────────┘   │ function      │
                     └───────────────┘
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

**Visual Example:**
```
┌────────────────┐
│File:           │
│src/core/auth.py│
└────────┬───────┘
         │
         │ CONTAINS
         ▼
┌────────────────┐                 ┌────────────────┐
│Function:       │◄────────────────┤CallSite in     │
│authenticate    │   RESOLVES_TO   │other file      │
└────────────────┘                 └────────┬───────┘
                                            │
                                            │ CONTAINS
                                            ▼
                                   ┌────────────────┐
                                   │File:           │
                                   │src/api/users.py│
                                   └────────────────┘
```

### Finding class hierarchy

```cypher
MATCH (c:Class {name: "BaseController"})
MATCH path = (subclass:Class)-[:INHERITS_FROM*]->(c)
RETURN path
```

**Visual Example:**
```
┌────────────────┐
│Class:          │
│BaseController  │
└────────┬───────┘
         ▲
         │ INHERITS_FROM
         │
┌────────┴───────┐         ┌────────────────┐
│Class:          │◄────────┤Class:          │
│UserController  │         │AdminController │
└────────────────┘         └────────────────┘
                             INHERITS_FROM
```