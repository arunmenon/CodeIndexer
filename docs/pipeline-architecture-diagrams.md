# Pipeline Architecture Diagrams

## System Architecture Overview

### High-Level Component Architecture
```mermaid
graph TB
    subgraph "Input Layer"
        A[Git Repository]
        B[File System]
        C[Direct Code Input]
    end
    
    subgraph "Ingestion Layer"
        D[Git Ingestion Agent]
        E[File Discovery]
        F[Language Detection]
    end
    
    subgraph "Parsing Layer"
        G[Tree-sitter Parser]
        H[Native Python Parser]
        I[Unified Parser Interface]
    end
    
    subgraph "Processing Layer"
        J[Strategy Factory]
        K[StandardProcessingStrategy]
        L[CompositePatternStrategy]
        M[StreamingIteratorStrategy]
    end
    
    subgraph "Extraction Layer"
        N[Function Extractor]
        O[Class Extractor]
        P[Call Site Extractor]
        Q[Import Extractor]
    end
    
    subgraph "Graph Layer"
        R[Enhanced Graph Builder]
        S[Node Creator]
        T[Relationship Mapper]
    end
    
    subgraph "Storage Layer"
        U[Neo4j Database]
        V[Knowledge Graph]
    end
    
    A --> D
    B --> E
    C --> F
    D --> E
    E --> F
    F --> G
    F --> H
    G --> I
    H --> I
    I --> J
    J --> K
    J --> L
    J --> M
    K --> N
    K --> O
    L --> P
    M --> Q
    N --> R
    O --> R
    P --> R
    Q --> R
    R --> S
    R --> T
    S --> U
    T --> U
    U --> V
```

## Detailed Component Interactions

### Tree-sitter Integration Flow
```mermaid
sequenceDiagram
    participant Client as Pipeline Client
    participant Factory as Strategy Factory
    participant Strategy as StandardProcessingStrategy
    participant Parser as UnifiedTreeSitterParser
    participant TSLib as Tree-sitter Library
    participant AST as AST Utils
    participant Graph as Graph Builder
    participant Neo4j as Neo4j Database

    Client->>Factory: process_repository(repo_path)
    Factory->>Strategy: create_strategy(ast_data, context)
    Strategy->>Parser: parse(code, language, file_path)
    Parser->>TSLib: parser.parse(code_bytes)
    TSLib-->>Parser: tree.root_node
    Parser->>Parser: _visit_tree(root_node, code_bytes)
    Parser-->>Strategy: {type, children, start_point, end_point, ...}
    
    Strategy->>Strategy: find_entity_in_ast(ast_root, "function_definition")
    Strategy->>AST: get_function_info(function_node)
    AST-->>Strategy: {name, params, start_line, end_line, ...}
    Strategy->>Strategy: create function_data dict
    Strategy-->>Graph: {functions: [...], classes: [...]}
    
    Graph->>Graph: _process_functions(functions, file_id, repository)
    Graph->>Graph: _batch_create_nodes("Function", function_nodes)
    Graph->>Neo4j: CREATE (f:Function {properties})
    Neo4j-->>Graph: success
    Graph-->>Client: processing_complete
```

### Error Handling and Fallback Chain
```mermaid
flowchart TD
    A[Source Code Input] --> B[Language Detection]
    B --> C{Tree-sitter Available?}
    
    C -->|Yes| D[Tree-sitter Parser]
    C -->|No| E[Native Python Parser]
    
    D --> F{Parsing Successful?}
    F -->|Yes| G[Tree-sitter AST]
    F -->|No| H[Log Error]
    H --> E
    
    E --> I{Native Parsing OK?}
    I -->|Yes| J[Python AST]
    I -->|No| K[Fallback to Simple Parser]
    
    G --> L[Strategy Processing]
    J --> L
    K --> M[Basic Text Analysis]
    
    L --> N[Function Extraction]
    M --> O[Limited Analysis]
    
    N --> P[Graph Creation]
    O --> P
    
    P --> Q[Neo4j Storage]
```

## Data Flow Architecture

### AST Processing Pipeline
```mermaid
graph LR
    subgraph "Raw Input"
        A1[Python File]
        A2[JavaScript File]
        A3[TypeScript File]
    end
    
    subgraph "Language Processing"
        B1[Python Tree-sitter]
        B2[JavaScript Tree-sitter]
        B3[TypeScript Tree-sitter]
    end
    
    subgraph "AST Formats"
        C1[Python AST JSON]
        C2[JavaScript AST JSON]
        C3[TypeScript AST JSON]
    end
    
    subgraph "Unified Processing"
        D[AST Format Detector]
        E[Entity Extractor]
        F[Relationship Mapper]
    end
    
    subgraph "Graph Entities"
        G1[Function Nodes]
        G2[Class Nodes]
        G3[Call Site Nodes]
        G4[Import Nodes]
    end
    
    subgraph "Neo4j Graph"
        H1[Function :Function]
        H2[Class :Class]
        H3[CallSite :CallSite]
        H4[ImportSite :ImportSite]
        H5[CONTAINS Relationships]
        H6[RESOLVES_TO Relationships]
    end
    
    A1 --> B1 --> C1
    A2 --> B2 --> C2
    A3 --> B3 --> C3
    
    C1 --> D
    C2 --> D
    C3 --> D
    
    D --> E --> G1
    E --> G2
    E --> G3
    E --> G4
    
    F --> H5
    F --> H6
    
    G1 --> H1
    G2 --> H2
    G3 --> H3
    G4 --> H4
```

### Function Extraction Detail Flow
```mermaid
flowchart TD
    A[Tree-sitter AST] --> B{Node Type Check}
    
    B -->|function_definition| C[Extract Function Info]
    B -->|class_definition| D[Extract Class Info]
    B -->|call| E[Extract Call Site]
    B -->|import_statement| F[Extract Import]
    B -->|Other| G[Continue Traversal]
    
    C --> H[Get Function Name]
    C --> I[Extract Parameters]
    C --> J[Get Line Numbers]
    C --> K[Extract Docstring]
    
    H --> L[Validate Function Data]
    I --> L
    J --> L
    K --> L
    
    L --> M{Valid Function?}
    M -->|Yes| N[Create Function Dict]
    M -->|No| O[Skip Function]
    
    N --> P[Add to Functions List]
    
    D --> Q[Similar Class Processing]
    E --> R[Similar Call Processing]
    F --> S[Similar Import Processing]
    
    P --> T[Return to Strategy]
    Q --> T
    R --> T
    S --> T
    O --> T
    G --> T
```

## Strategy Pattern Architecture

### Strategy Selection Logic
```mermaid
graph TD
    A[AST Data Input] --> B[Calculate File Size]
    B --> C{Size Analysis}
    
    C -->|< 100KB| D[StandardProcessingStrategy]
    C -->|100KB - 500KB| E[CompositePatternStrategy]
    C -->|500KB - 5MB| F[InMemoryIteratorStrategy]
    C -->|> 5MB| G[StreamingIteratorStrategy]
    
    D --> H[Direct AST Traversal]
    E --> I[Composite Pattern Processing]
    F --> J[Iterator-based Processing]
    G --> K[Streaming Processing]
    
    H --> L[Extract Entities]
    I --> L
    J --> L
    K --> L
    
    L --> M[Return Strategy Result]
    
    subgraph "Strategy Result Format"
        N[functions: List]
        O[classes: List]
        P[call_sites: List]
        Q[import_sites: List]
        R[status: success/error]
    end
    
    M --> N
    M --> O
    M --> P
    M --> Q
    M --> R
```

### Enhanced Graph Builder Processing
```mermaid
sequenceDiagram
    participant Pipeline as Pipeline Controller
    participant Builder as Enhanced Graph Builder
    participant Strategy as Processing Strategy
    participant Neo4j as Neo4j Database
    participant Stats as Statistics Tracker

    Pipeline->>Builder: process_ast(ast_data, repository, url, commit, branch)
    Builder->>Builder: _create_file_node(file_path, language, repository)
    Builder->>Strategy: process_ast(ast_data, context)
    
    Strategy->>Strategy: _extract_functions(ast_root, file_id, file_path, language, repository)
    Strategy->>Strategy: _extract_classes(ast_root, file_id, file_path, language, repository)
    Strategy-->>Builder: {status: "success", functions: [...], classes: [...]}
    
    Builder->>Builder: _process_functions(functions, file_id, repository)
    Builder->>Builder: _process_classes(classes, file_id, repository)
    
    Builder->>Neo4j: _batch_create_nodes("Function", function_nodes)
    Builder->>Neo4j: _batch_create_nodes("Class", class_nodes)
    
    Builder->>Stats: graph_stats["functions"] += len(functions)
    Builder->>Stats: graph_stats["classes"] += len(classes)
    
    Neo4j-->>Builder: creation_success
    Builder-->>Pipeline: {status: "success", entity_count: N, ...}
```

## Performance Optimization Architecture

### Batch Processing Flow
```mermaid
graph LR
    subgraph "Input Batch"
        A1[File 1]
        A2[File 2]
        A3[File N]
    end
    
    subgraph "Parallel Processing"
        B1[Worker 1]
        B2[Worker 2]
        B3[Worker N]
    end
    
    subgraph "AST Generation"
        C1[AST 1]
        C2[AST 2]  
        C3[AST N]
    end
    
    subgraph "Entity Extraction"
        D1[Functions 1]
        D2[Functions 2]
        D3[Functions N]
    end
    
    subgraph "Batch Aggregation"
        E[Combined Function List]
        F[Combined Class List]
        G[Combined Call Sites]
    end
    
    subgraph "Database Operations"
        H[Batch CREATE Functions]
        I[Batch CREATE Classes]
        J[Batch CREATE Relationships]
    end
    
    A1 --> B1 --> C1 --> D1
    A2 --> B2 --> C2 --> D2
    A3 --> B3 --> C3 --> D3
    
    D1 --> E
    D2 --> E
    D3 --> E
    
    E --> H
    F --> I
    G --> J
```

### Memory Management Strategy
```mermaid
flowchart TD
    A[Large Repository Input] --> B{Memory Assessment}
    
    B -->|Low Memory| C[Streaming Strategy]
    B -->|Medium Memory| D[Batch Strategy]
    B -->|High Memory| E[In-Memory Strategy]
    
    C --> F[Process Files One by One]
    D --> G[Process Files in Batches]
    E --> H[Load All Files in Memory]
    
    F --> I[Immediate Write to Neo4j]
    G --> J[Batch Write to Neo4j]
    H --> K[Bulk Write to Neo4j]
    
    I --> L[Memory Efficient]
    J --> M[Balanced Performance]
    K --> N[Maximum Performance]
    
    L --> O[Handle Large Repos]
    M --> O
    N --> O
```

## Error Handling and Recovery

### Comprehensive Error Flow
```mermaid
graph TD
    A[Processing Start] --> B[Tree-sitter Init]
    B --> C{Init Success?}
    
    C -->|No| D[Log Tree-sitter Error]
    C -->|Yes| E[Parse File]
    
    D --> F[Fallback to Native Parser]
    E --> G{Parse Success?}
    
    G -->|No| H[Log Parse Error]
    G -->|Yes| I[Extract Functions]
    
    H --> F
    F --> I
    I --> J{Extraction Success?}
    
    J -->|No| K[Log Extraction Error]
    J -->|Yes| L[Create Graph Nodes]
    
    K --> M[Partial Processing]
    L --> N{Node Creation Success?}
    
    N -->|No| O[Log Graph Error]
    N -->|Yes| P[Success]
    
    O --> Q[Retry with Backoff]
    M --> R[Continue with Next File]
    P --> S[Process Next File]
    Q --> S
    R --> S
```

This comprehensive documentation captures all the architectural improvements, data flows, and technical details of the ingestion pipeline transformation.