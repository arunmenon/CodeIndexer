# Troubleshooting Guide

This guide helps you diagnose and fix common issues that may arise when using CodeIndexer.

## Installation Issues

### Problem: Import errors when running CodeIndexer

**Symptoms:**
```
ImportError: No module named 'code_indexer'
```

**Solutions:**
1. Ensure you've installed the package in development mode:
   ```bash
   pip install -e .
   ```

2. Verify your virtual environment is activated:
   ```bash
   # On Linux/macOS
   source venv/bin/activate
   
   # On Windows
   venv\Scripts\activate
   ```

3. Check that installation completed successfully:
   ```bash
   pip list | grep code-indexer
   ```

### Problem: Tree-sitter installation fails

**Symptoms:**
```
ImportError: No module named 'tree_sitter'
```

**Solutions:**
1. Install Tree-sitter and language libraries manually:
   ```bash
   pip install tree-sitter
   pip install tree-sitter-python tree-sitter-javascript
   ```

2. Ensure you have a C compiler installed (required for Tree-sitter):
   - On macOS: `xcode-select --install`
   - On Ubuntu: `apt-get install build-essential`
   - On Windows: Install Visual C++ build tools

## Neo4j Connection Issues

### Problem: Cannot connect to Neo4j

**Symptoms:**
```
Failed to establish connection to Neo4j database
```

**Solutions:**
1. Verify Neo4j is running:
   ```bash
   # If using Docker
   docker ps | grep neo4j
   
   # If using Neo4j Desktop
   # Check that the database is started in the application
   ```

2. Check connection parameters:
   ```bash
   # Use explicit parameters
   python -m code_indexer.ingestion.cli.run_pipeline \
       --repo-path /path/to/repo \
       --neo4j-uri bolt://localhost:7687 \
       --neo4j-user neo4j \
       --neo4j-password your_password
   ```

3. Ensure firewall is not blocking connections:
   - Neo4j Bolt protocol uses port 7687
   - Neo4j Browser uses port 7474

### Problem: Authentication failed

**Symptoms:**
```
Neo4j authentication failed
```

**Solutions:**
1. Reset Neo4j password:
   - In Neo4j Desktop: Right-click database → Manage → Change password
   - With Docker: 
     ```bash
     docker exec -it neo4j cypher-shell -u neo4j -p current_password
     ALTER CURRENT USER SET PASSWORD FROM 'current_password' TO 'new_password';
     ```

2. Verify you're using the correct credentials:
   ```bash
   # Test connection with cypher-shell
   cypher-shell -a bolt://localhost:7687 -u neo4j -p your_password
   ```

## Ingestion Pipeline Issues

### Problem: Git ingestion fails

**Symptoms:**
```
ERROR: Failed to clone repository
```

**Solutions:**
1. Check repository URL or path:
   ```bash
   # For local repos, use absolute path
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path $(pwd)/my_repo
   ```

2. Verify Git credentials for private repositories:
   ```bash
   # Use SSH URL instead of HTTPS
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path git@github.com:username/repo.git
   ```

3. For large repositories, increase timeout:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --git-timeout 300
   ```

### Problem: Parsing errors with Tree-sitter

**Symptoms:**
```
ERROR: Failed to parse file: syntax error
```

**Solutions:**
1. Check if the file language is supported:
   - Currently supported: Python, JavaScript, TypeScript, Java
   - Add languages with: `--languages python,javascript,java`

2. Update Tree-sitter to the latest version:
   ```bash
   pip install --upgrade tree-sitter
   ```

3. For files with syntax errors, use fault-tolerant mode:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --fault-tolerant
   ```

### Problem: Out of memory during graph building

**Symptoms:**
```
ERROR: Java heap space error
```

**Solutions:**
1. Increase Neo4j memory allocation:
   - In Neo4j Desktop: Right-click database → Settings → Initial Heap Size/Max Heap Size
   - With Docker:
     ```bash
     docker run -e NEO4J_dbms_memory_heap_max__size=4G -e NEO4J_dbms_memory_heap_initial__size=1G
     ```

2. Process the repository in smaller batches:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --batch-size 1000
   ```

3. Use a more efficient resolution strategy for large codebases:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy hashmap
   ```

## Resolution Issues

### Problem: Function calls not being resolved

**Symptoms:**
- CallSite nodes exist but don't have RESOLVES_TO relationships
- Queries for function calls return no results

**Solutions:**
1. Check if resolution was skipped:
   ```bash
   # Ensure immediate resolution is enabled
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --immediate-resolution
   ```

2. Run manual resolution:
   ```bash
   python -m code_indexer.tools.resolution_tool --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password password
   ```

3. Create necessary indexes in Neo4j:
   ```cypher
   CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name, f.repository);
   CREATE INDEX callsite_target IF NOT EXISTS FOR (c:CallSite) ON (c.target_name, c.repository, c.resolved);
   ```

### Problem: Poor resolution quality

**Symptoms:**
- Function calls resolve to incorrect targets
- Multiple ambiguous matches

**Solutions:**
1. Use a more precise resolution strategy:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-strategy join
   ```

2. Adjust confidence threshold:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --resolution-threshold 0.8
   ```

3. For large codebases with many similarly named functions, add namespace resolution:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --use-namespace-resolution
   ```

## Performance Issues

### Problem: Slow indexing for large repositories

**Symptoms:**
- Indexing takes hours for medium-sized repositories
- High CPU or memory usage

**Solutions:**
1. Use incremental indexing for subsequent runs:
   ```bash
   # First run (full indexing)
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --full-indexing
   
   # Subsequent runs (incremental)
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo
   ```

2. Increase parallel processing:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --workers 8
   ```

3. Skip unnecessary stages:
   ```bash
   # If you only need code structure, skip chunking and embedding
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --skip-chunk --skip-embed
   ```

4. Use profile mode to identify bottlenecks:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --profile
   ```

### Problem: Slow Neo4j queries

**Symptoms:**
- Graph queries take minutes to execute
- Browser visualization is laggy

**Solutions:**
1. Ensure proper indexes are created:
   ```cypher
   CREATE INDEX file_repo_path IF NOT EXISTS FOR (f:File) ON (f.repository, f.path);
   CREATE INDEX function_name IF NOT EXISTS FOR (f:Function) ON (f.name, f.repository);
   CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name, c.repository);
   CREATE INDEX callsite_target IF NOT EXISTS FOR (c:CallSite) ON (c.target_name, c.repository, c.resolved);
   ```

2. Optimize Neo4j memory settings:
   - Increase heap size for large graphs
   - Adjust page cache size for better performance

3. Limit result sets in queries:
   ```cypher
   // Use LIMIT to restrict results
   MATCH (f:Function)-[:CONTAINS]->(cs:CallSite)
   RETURN f.name, count(cs) as calls
   ORDER BY calls DESC
   LIMIT 100
   ```

## Common Error Messages

### "No such file or directory"

This usually indicates an incorrect path to the repository or output directory.

**Solution:**
```bash
# Use absolute paths
python -m code_indexer.ingestion.cli.run_pipeline --repo-path $(realpath ./my_repo) --output-dir $(realpath ./output)
```

### "Neo4j database is not available"

This indicates Neo4j is not running or not accessible.

**Solution:**
```bash
# Start Neo4j if using Docker
docker start neo4j

# Check connection with a simple query
cypher-shell -a bolt://localhost:7687 -u neo4j -p password "RETURN 1"
```

### "Language not supported"

This indicates Tree-sitter doesn't have a grammar for the language.

**Solution:**
```bash
# Install additional language support
pip install tree-sitter-<language>

# Specify languages to process
python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --languages python,javascript,java
```

## Getting Help

If you encounter issues not covered in this guide:

1. Check the logs for detailed error information:
   ```bash
   python -m code_indexer.ingestion.cli.run_pipeline --repo-path /path/to/repo --verbose --log-file debug.log
   ```

2. Open an issue on GitHub with:
   - Detailed description of the problem
   - Steps to reproduce
   - Error messages and logs
   - Environment information (OS, Python version, Neo4j version)

3. For Neo4j-specific issues, consult the [Neo4j documentation](https://neo4j.com/docs/).