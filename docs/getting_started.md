# Getting Started with CodeIndexer

This guide will help you get up and running with CodeIndexer quickly. We'll walk through installation, basic configuration, and a simple example to index a small repository.

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.8 or later
- Git
- Neo4j 4.4 or later
- pip (Python package manager)

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/CodeIndexer.git
   cd CodeIndexer
   ```

2. **Set up a virtual environment** (recommended)

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install CodeIndexer and dependencies**

   ```bash
   pip install -e .
   ```

4. **Verify installation**

   ```bash
   python -c "import code_indexer; print('Installation successful')"
   ```

## Setting up Neo4j

1. **Start Neo4j**

   If you have Neo4j Desktop installed, create and start a new database.
   
   Alternatively, you can use Docker:

   ```bash
   docker run \
       --name neo4j \
       -p 7474:7474 -p 7687:7687 \
       -e NEO4J_AUTH=neo4j/password \
       neo4j:4.4
   ```

2. **Create required indexes**

   Run the following Cypher queries in Neo4j Browser (http://localhost:7474):

   ```cypher
   CREATE INDEX file_repo_path IF NOT EXISTS FOR (f:File) ON (f.repository, f.path);
   CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name, f.repository);
   CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name, c.repository);
   CREATE INDEX callsite_target IF NOT EXISTS FOR (c:CallSite) ON (c.target_name, c.repository, c.resolved);
   ```

## Your First Indexing Run

Let's index a small open-source repository to see CodeIndexer in action.

1. **Choose a small Python repository**

   We'll use a small Python project for this example:

   ```bash
   mkdir -p workspace
   cd workspace
   git clone https://github.com/pallets/click.git
   cd ..
   ```

2. **Run the indexing pipeline**

   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline \
       --repo-path ./workspace/click \
       --output-dir ./output \
       --full-indexing \
       --verbose \
       --neo4j-uri bolt://localhost:7687 \
       --neo4j-user neo4j \
       --neo4j-password password
   ```

3. **Monitor progress**

   You'll see logs showing:
   - Git cloning/updating
   - File parsing
   - AST extraction
   - Graph node creation
   - Relationship resolution

4. **Verify results**

   After indexing completes, check Neo4j Browser (http://localhost:7474) to explore the code graph:

   ```cypher
   // Count different node types
   MATCH (f:File) RETURN count(f) as files
   MATCH (c:Class) RETURN count(c) as classes
   MATCH (f:Function) RETURN count(f) as functions
   MATCH (c:CallSite) RETURN count(c) as callSites
   
   // View file structure
   MATCH (f:File)
   WHERE f.repository CONTAINS "click"
   RETURN f.path, f.language
   LIMIT 10
   
   // Find the most called functions
   MATCH (cs:CallSite)-[:RESOLVES_TO]->(f:Function)
   WHERE cs.repository CONTAINS "click"
   RETURN f.name, count(cs) as calls
   ORDER BY calls DESC
   LIMIT 10
   ```

## Understanding the Output

After indexing, you'll have:

1. **Knowledge Graph in Neo4j**
   - File nodes representing source files
   - Class and Function nodes representing code entities
   - CallSite and ImportSite nodes for cross-file references
   - Relationships showing code structure and dependencies

2. **Output Directory**
   - Git extraction results
   - AST parsing results
   - Graph building logs

## Next Steps

Now that you've completed your first indexing run, you can:

1. [Explore the graph schema](graph_schema.md) to understand the node types and relationships
2. [Learn about the ingestion pipeline](ingestion-flow.md) to understand how code is processed
3. [Study the placeholder pattern](placeholder_pattern.md) to see how cross-file relationships are resolved
4. Try indexing your own codebase by pointing to a different repository

## Troubleshooting

### Common Issues

1. **Neo4j connection errors**
   - Verify Neo4j is running: `docker ps` or check Neo4j Desktop
   - Check credentials and connection string
   - Ensure ports 7474 and 7687 are accessible

2. **Tree-sitter parsing errors**
   - Make sure tree-sitter is properly installed
   - Check if the language is supported
   - Try running with `--verbose` for detailed logs

3. **Memory issues with large codebases**
   - Increase Neo4j memory: `docker run -e NEO4J_dbms_memory_heap_max__size=4G ...`
   - Use chunked processing with `--batch-size` option
   - Consider using the `hashmap` resolution strategy: `--resolution-strategy hashmap`

4. **Permission errors**
   - Check if you have write access to the output directory
   - Verify you have read access to the repository

For comprehensive troubleshooting information, see the [Troubleshooting Guide](./troubleshooting.md) or [open an issue](https://github.com/yourusername/CodeIndexer/issues) if you encounter persistent problems.