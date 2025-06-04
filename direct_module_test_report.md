# Module Test Report (Direct File Analysis)

## Summary

- Total modules tested: 13
- Successfully loaded: 12
- Failed to load: 1
- Total classes found: 10
- Total functions found: 13

## Module Details

### code_indexer/tools/ast_extractor.py

✅ **Load Successful**

**Classes (1):**

- `ASTExtractor`

**Functions (1):**

- `create_ast_extractor`

### code_indexer/tools/tree_sitter_parser.py

✅ **Load Successful**

**Classes (1):**

- `TreeSitterParser`

**Functions (0):**

- *No functions found*

### code_indexer/tools/git_tool.py

✅ **Load Successful**

**Classes (1):**

- `GitTool`

**Functions (0):**

- *No functions found*

### code_indexer/tools/neo4j_tool.py

❌ **Load Failed**

### code_indexer/tools/vector_store_interface.py

✅ **Load Successful**

**Classes (2):**

- `SearchResult`
- `VectorStoreInterface`

**Functions (0):**

- *No functions found*

### code_indexer/tools/vector_store_factory.py

✅ **Load Successful**

**Classes (1):**

- `VectorStoreFactory`

**Functions (0):**

- *No functions found*

### code_indexer/ingestion/direct/ast_extractor.py

✅ **Load Successful**

**Classes (0):**

- *No classes found*

**Functions (1):**

- `create_tree_sitter_extractor`

### code_indexer/ingestion/direct/git_ingestion.py

✅ **Load Successful**

**Classes (1):**

- `DirectGitIngestionRunner`

**Functions (0):**

- *No functions found*

### code_indexer/ingestion/direct/graph_builder.py

✅ **Load Successful**

**Classes (2):**

- `DirectGraphBuilderRunner`
- `Neo4jToolWrapper`

**Functions (0):**

- *No functions found*

### code_indexer/ingestion/pipeline.py

✅ **Load Successful**

**Classes (0):**

- *No classes found*

**Functions (1):**

- `run_pipeline`

### code_indexer/utils/ast_utils.py

✅ **Load Successful**

**Classes (0):**

- *No classes found*

**Functions (4):**

- `ast_to_dict`
- `find_entity_in_ast`
- `get_class_info`
- `get_function_info`

### code_indexer/utils/repo_utils.py

✅ **Load Successful**

**Classes (0):**

- *No classes found*

**Functions (3):**

- `count_lines_of_code`
- `get_file_hash`
- `is_binary_file`

### code_indexer/utils/vector_store_utils.py

✅ **Load Successful**

**Classes (1):**

- `FilterBuilder`

**Functions (3):**

- `format_code_metadata`
- `get_code_metadata_schema`
- `load_vector_store_config`
