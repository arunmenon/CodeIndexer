# End-to-End Example: Indexing and Analyzing a Python Project

This document walks through a complete example of using CodeIndexer to process a real Python project, explaining each step of the pipeline and showing how to analyze the resulting code graph.

## Overview

We'll use the popular `click` library as our example, a command-line interface creation package for Python. This walkthrough will demonstrate:

1. Setting up the environment
2. Running the full indexing pipeline
3. Exploring the code graph in Neo4j
4. Answering code understanding questions using the graph

## Prerequisites

Ensure you have:
- CodeIndexer installed (see [Getting Started Guide](getting_started.md))
- Neo4j running
- A copy of the click repository (we'll clone it as part of this walkthrough)

## Step 1: Prepare the Repository

First, let's clone the click repository to a workspace directory:

```bash
mkdir -p workspace
cd workspace
git clone https://github.com/pallets/click.git
cd ..
```

## Step 2: Run the Indexing Pipeline

We'll run the full pipeline with detailed logging:

```bash
python -m code_indexer.ingestion.cli.run_pipeline \
    --repo-path ./workspace/click \
    --output-dir ./click_output \
    --full-indexing \
    --verbose \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j \
    --neo4j-password password
```

### Understanding What's Happening

Let's break down what each stage of the pipeline is doing:

#### Git Ingestion Stage

Output should look similar to:
```
INFO:code_indexer.ingestion.direct.git_ingestion:Processing repository: click
INFO:code_indexer.ingestion.direct.git_ingestion:Cloning repository from ./workspace/click
INFO:code_indexer.tools.git_tool:Cloning repository from ./workspace/click to /tmp/tmp_click_repo
INFO:code_indexer.tools.git_tool:Repository cloned successfully
INFO:code_indexer.tools.git_tool:Found 59 Python files
```

This stage:
1. Clones or updates the repository
2. Identifies relevant files (Python in this case)
3. Extracts file content and metadata

#### Code Parsing Stage

Output should show:
```
INFO:code_indexer.ingestion.direct.ast_extractor:Parsing 59 Python files
INFO:code_indexer.tools.tree_sitter_parser:Parsing file: src/click/core.py
INFO:code_indexer.tools.tree_sitter_parser:Parsed 4328 lines successfully
```

This stage:
1. Uses Tree-sitter to parse each file
2. Extracts Abstract Syntax Trees (ASTs)
3. Identifies functions, classes, and other code structures

#### Graph Building Stage

Output will include:
```
INFO:code_indexer.ingestion.direct.graph_builder:Creating graph nodes for 59 files
INFO:code_indexer.ingestion.direct.graph_builder:Created 59 File nodes
INFO:code_indexer.ingestion.direct.graph_builder:Created 47 Class nodes
INFO:code_indexer.ingestion.direct.graph_builder:Created 312 Function nodes
INFO:code_indexer.ingestion.direct.graph_builder:Created 843 CallSite nodes
INFO:code_indexer.ingestion.direct.graph_builder:Resolving relationships...
```

This stage:
1. Creates nodes in Neo4j for each entity (files, classes, functions)
2. Creates placeholder nodes for call sites and import sites
3. Establishes structural relationships (CONTAINS, INHERITS_FROM)
4. Resolves cross-file references (RESOLVES_TO)

## Step 3: Exploring the Code Graph

Now that we've created our code graph, let's explore it using Neo4j's Cypher query language.

### Basic Exploration Queries

Open Neo4j Browser (http://localhost:7474) and try these queries:

#### 1. Code Structure Overview

```cypher
// Count each type of node
MATCH (f:File) WHERE f.repository CONTAINS 'click' RETURN count(f) as Files
MATCH (c:Class) WHERE c.repository CONTAINS 'click' RETURN count(c) as Classes
MATCH (f:Function) WHERE f.repository CONTAINS 'click' RETURN count(f) as Functions
MATCH (cs:CallSite) WHERE cs.repository CONTAINS 'click' RETURN count(cs) as CallSites
```

#### 2. View Project Files

```cypher
// Show main project files
MATCH (f:File)
WHERE f.repository CONTAINS 'click'
RETURN f.path, f.language
ORDER BY f.path
LIMIT 20
```

#### 3. Find Core Classes

```cypher
// Find classes with the most methods
MATCH (c:Class)<-[:CONTAINS]-(f:File)
WHERE f.repository CONTAINS 'click'
MATCH (c)-[:CONTAINS]->(m:Function)
RETURN c.name as ClassName, count(m) as MethodCount, f.path as FilePath
ORDER BY MethodCount DESC
LIMIT 10
```

## Step 4: Answering Code Understanding Questions

Let's use our code graph to answer some common code understanding questions:

### Question 1: What's the main entry point for the Click library?

```cypher
// Find functions imported directly at the package level
MATCH (f:File {path: "src/click/__init__.py"})-[:CONTAINS]->(i:ImportSite)
MATCH (i)-[:RESOLVES_TO]->(target)
RETURN i.import_name, target.name, labels(target)
```

### Question 2: How does Click handle command-line arguments?

```cypher
// Find classes related to argument handling
MATCH (c:Class)
WHERE c.repository CONTAINS 'click' AND c.name CONTAINS 'Argument'
MATCH (c)-[:CONTAINS]->(m:Function)
RETURN c.name, m.name, m.start_line, m.end_line
ORDER BY c.name, m.name
```

### Question 3: What's the inheritance hierarchy?

```cypher
// Visualize class inheritance
MATCH path = (c:Class)-[:INHERITS_FROM*1..3]->(parent:Class)
WHERE c.repository CONTAINS 'click'
RETURN path
LIMIT 25
```

### Question 4: What are the most called functions?

```cypher
// Find the most referenced functions
MATCH (cs:CallSite)-[:RESOLVES_TO]->(f:Function)
WHERE cs.repository CONTAINS 'click'
RETURN f.name, count(cs) as callCount
ORDER BY callCount DESC
LIMIT 10
```

## Step 5: Advanced Analysis

### Finding Dead Code

```cypher
// Find functions that are never called
MATCH (f:Function)<-[:CONTAINS]-(parent)
WHERE f.repository CONTAINS 'click' AND NOT f.name STARTS WITH '_'
AND NOT EXISTS {
  MATCH (cs:CallSite)-[:RESOLVES_TO]->(f)
}
RETURN f.name, labels(parent)[0] as ParentType, parent.name as ParentName
ORDER BY ParentType, ParentName
```

### Analyzing Dependencies Between Modules

```cypher
// Create a module dependency graph
MATCH (f1:File)-[:CONTAINS]->(i:ImportSite)-[:RESOLVES_TO]->(:Function)<-[:CONTAINS]-(f2:File)
WHERE f1.repository CONTAINS 'click' AND f2.repository CONTAINS 'click'
WITH f1.path as importing, f2.path as imported, count(*) as strength
RETURN importing, imported, strength
ORDER BY strength DESC
LIMIT 20
```

## Step 6: Visualizing the Results

Neo4j Browser provides visualization capabilities. Try this query to visualize the core class structure:

```cypher
// Visualize core classes and their relationships
MATCH (c:Class)<-[:CONTAINS]-(f:File)
WHERE f.repository CONTAINS 'click' AND f.path CONTAINS 'core.py'
OPTIONAL MATCH (c)-[:INHERITS_FROM]->(parent:Class)
OPTIONAL MATCH (c)-[:CONTAINS]->(m:Function)
RETURN c, parent, m
LIMIT 50
```

## Conclusion

This end-to-end example demonstrated how CodeIndexer processes a real Python project and creates a knowledge graph. You can:

1. **Extract code structure** - Identify files, classes, functions, and their relationships
2. **Analyze code semantics** - Understand how components interact across files
3. **Query for insights** - Find dead code, dependencies, and core functionality
4. **Visualize relationships** - See inheritance hierarchies and call graphs

For more complex codebases, the same principles apply, but you may need to adjust resolution strategies and Neo4j memory settings as described in the [ingestion flow documentation](ingestion-flow.md).

## Next Steps

- Try indexing your own projects
- Create custom Cypher queries for your specific analysis needs
- Explore how to use the graph for documentation generation
- Check out the [placeholder pattern](placeholder_pattern.md) to understand cross-file resolution in detail
- If you encounter any issues, refer to the [Troubleshooting Guide](troubleshooting.md)