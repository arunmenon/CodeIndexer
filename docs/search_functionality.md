# Code Indexer Search Functionality

This document describes the Code Indexer's search functionality, which enables natural language code search across codebases.

## Overview

The search functionality allows users to query the code knowledge base using natural language and get relevant code snippets and explanations. It combines vector similarity search for semantic matching with graph-based search for structural code understanding.

## Architecture

The search system consists of five main agents that work together:

1. **QueryAgent** - Processes natural language queries and extracts intent
2. **VectorSearchAgent** - Performs similarity search using code embeddings
3. **GraphSearchAgent** - Executes structural code queries using the knowledge graph
4. **AnswerComposerAgent** - Synthesizes search results into coherent answers
5. **SearchOrchestratorAgent** - Coordinates the end-to-end search flow

### Query Flow

The search process follows these steps:

1. User submits a natural language query
2. QueryAgent analyzes the query to determine intent and generate query embeddings
3. Search agents (Vector and Graph) execute searches in parallel
4. AnswerComposerAgent combines results and generates a natural language answer
5. Results are returned to the user with relevant code snippets

## Usage

### API

The Code Indexer provides a simple API for accessing search functionality:

```python
from code_indexer.api.search_api import CodeSearchAPI

# Initialize the search API with an agent context
search_api = CodeSearchAPI(context)

# Basic search
result = search_api.search("How does the authentication system work?")

# Search with options
result = search_api.search(
    query="Find all error handling code",
    search_type="hybrid",  # hybrid, vector, graph
    max_results=20,
    filters={"language": "python"}
)

# Specialized search methods
result = search_api.search_by_file("/path/to/file.py")
result = search_api.search_by_function("authenticate_user")
result = search_api.search_by_class("UserManager")
result = search_api.explain_code("process_payment")
```

### CLI

The Code Indexer also provides a command-line interface for search:

```bash
# Basic search
python -m code_indexer.cli.search_cli --query "How does the authentication system work?"

# Search by file
python -m code_indexer.cli.search_cli --file "/path/to/file.py"

# Search by function
python -m code_indexer.cli.search_cli --function "authenticate_user"

# Search by class
python -m code_indexer.cli.search_cli --class "UserManager"

# Explain code
python -m code_indexer.cli.search_cli --explain "process_payment"

# Advanced options
python -m code_indexer.cli.search_cli --query "Find all error handling" \
  --search-type vector \
  --max-results 20 \
  --filter "language=python" \
  --json \
  --output results.json
```

## Query Types

The search system supports various types of queries:

1. **Definition Queries** - Find where code entities are defined
   - "Where is the `authenticate_user` function defined?"
   - "Show me the definition of the `UserManager` class"

2. **Usage Queries** - Find where code entities are used
   - "Where is the `authenticate_user` function called?"
   - "How is the `UserManager` class used?"

3. **Explanation Queries** - Explain how code works
   - "How does the authentication system work?"
   - "Explain the payment processing flow"

4. **Inheritance Queries** - Find class hierarchies
   - "What classes inherit from `BaseController`?"
   - "Show me the inheritance hierarchy for `UserManager`"

5. **General Information Queries** - Find code related to concepts
   - "Find all code related to error handling"
   - "Show me logging implementation"

## Search Types

The system supports three search types:

1. **Hybrid Search** (default) - Combines vector and graph search for comprehensive results
2. **Vector Search** - Semantic search using code embeddings
3. **Graph Search** - Structure-based search using code knowledge graph

## Response Format

Search responses include:

```json
{
  "success": true,
  "query": "Original query",
  "answer": "Natural language answer to the query",
  "code_snippets": [
    {
      "entity_id": "function_name",
      "entity_type": "function",
      "file_path": "/path/to/file.py",
      "language": "python",
      "code": "def function_name():\n    # Function content\n    return result"
    }
  ],
  "total_results": 10,
  "search_type": "hybrid"
}
```

## Advanced Features

### Multi-Query Expansion

For complex queries, the system can expand the original query into multiple variations to improve recall. This is handled automatically by the QueryAgent.

### Result Reranking

Search results from different sources are combined and reranked based on relevance to the query. The AnswerComposerAgent handles this merging and ranking process.

### Metadata Filtering

Results can be filtered by metadata such as:

- Language (`python`, `javascript`, etc.)
- Entity type (`function`, `class`, `method`, etc.)
- File path patterns
- Repository information

### Explanation Generation

The system can generate explanations of how code works by analyzing both the code structure and content.

## Configuration

The search functionality can be configured through the vector store configuration file:

```yaml
search:
  # Default search type (hybrid, vector, graph)
  default_search_type: "hybrid"
  
  # Whether to enable parallel search
  enable_parallel: true
  
  # Default number of results to return
  default_max_results: 10
  
  # Whether to enable multi-query expansion
  multi_query_expansion: true
  
  # Number of expanded queries to generate
  expansion_count: 3
  
  # Minimum similarity score for vector results (0-1)
  minimum_score: 0.7
  
  # Maximum number of code snippets to include in responses
  max_code_snippets: 3
  
  # Whether to include explanations in responses
  include_explanations: true
```

## Implementation Details

### QueryAgent

The QueryAgent is responsible for:

- Analyzing natural language queries to determine intent
- Extracting entities and key phrases
- Generating query embeddings
- Creating search specifications

### VectorSearchAgent

The VectorSearchAgent performs:

- Similarity search using query embeddings
- Filtering based on metadata
- Result scoring and ranking

### GraphSearchAgent

The GraphSearchAgent handles:

- Structural code queries using Neo4j
- Finding definitions, usages, and relationships
- Traversing code graphs for complex relationships

### AnswerComposerAgent

The AnswerComposerAgent:

- Merges results from different search agents
- Reranks combined results
- Generates natural language answers
- Selects the most relevant code snippets

### SearchOrchestratorAgent

The SearchOrchestratorAgent:

- Coordinates the end-to-end search process
- Parallelizes search operations
- Handles error cases and fallbacks

## Extending the Search Functionality

### Adding New Query Types

To add support for new query types:

1. Update the QueryAgent's `_detect_intent` method to recognize the new intent
2. Add appropriate handling in the GraphSearchAgent for structural queries
3. Update the AnswerComposerAgent to generate answers for the new query type

### Improving Result Ranking

The result ranking logic is in the AnswerComposerAgent's `_rank_results` method. Customize this to adjust the ranking criteria.

### Adding Metadata Filters

To add new metadata filters:

1. Update the vector store schema to include the new metadata
2. Update the QueryAgent's `_enhance_filters` method to detect and add the filters
3. Ensure the VectorSearchAgent and GraphSearchAgent support the new filters