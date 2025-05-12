# Milvus Integration for Code Indexer

This document describes how to set up and use Milvus as the vector database for the Code Indexer system.

## Overview

The Code Indexer's Milvus integration provides a high-performance vector database backend for storing and retrieving code embeddings. Milvus is specifically designed for similarity search at scale, making it ideal for code search applications.

## Setup

### Prerequisites

- Docker and Docker Compose (for running Milvus)
- Python 3.8+ with the pymilvus package installed

### Installation

1. Install the pymilvus package:

```bash
pip install pymilvus
```

2. Start Milvus using Docker Compose:

```bash
# Clone the Code Indexer repository if you haven't already
git clone https://github.com/yourusername/CodeIndexer.git
cd CodeIndexer

# Start Milvus using Docker Compose
docker-compose -f docker-compose.milvus.yml up -d
```

3. Verify Milvus is running:

```bash
# Check Milvus containers
docker ps | grep milvus

# You should see three containers:
# - milvus-standalone
# - milvus-etcd
# - milvus-minio
```

## Configuration

The Milvus integration is configured through the `vector_store_config.yaml` file. Here's a sample configuration:

```yaml
vector_store:
  type: "milvus"
  default_collection: "code_embeddings"
  embedding_dimension: 1536  # For OpenAI embeddings
  
  milvus:
    # Connection parameters
    host: "localhost"
    port: 19530
    user: ""
    password: ""
    secure: false
    connection_alias: "code_indexer"
    
    # Index parameters
    index_type: "HNSW"  # Options: HNSW, IVF_FLAT, FLAT
    index_params:
      M: 16             # HNSW parameter: max number of edges per node
      efConstruction: 200  # HNSW parameter: size of the dynamic candidate list for building
    
    # Search parameters
    search_ef: 64       # HNSW parameter: size of the dynamic candidate list for searching
    search_nprobe: 10   # IVF parameter: number of clusters to search
```

### Configuration Options

#### Connection Parameters

- `host`: Milvus server hostname (default: "localhost")
- `port`: Milvus server port (default: 19530)
- `user`: Username for authentication (if enabled)
- `password`: Password for authentication (if enabled)
- `secure`: Whether to use TLS for the connection (default: false)
- `connection_alias`: Alias for the connection (default: "code_indexer")

#### Index Parameters

- `index_type`: Type of index to create (options: "HNSW", "IVF_FLAT", "FLAT")
- `index_params`: Parameters for the index type
  - For HNSW:
    - `M`: Maximum number of edges per node (default: 16)
    - `efConstruction`: Size of the dynamic candidate list for building (default: 200)
  - For IVF_FLAT:
    - `nlist`: Number of clusters (default: 1024)

#### Search Parameters

- `search_ef`: For HNSW, size of the dynamic candidate list for searching (default: 64)
- `search_nprobe`: For IVF, number of clusters to search (default: 10)

#### Performance Tuning

- `connection_pool_size`: Size of the connection pool (default: 10)
- `batch_size`: Number of vectors to process in a batch (default: 1000)
- `timeout`: Operation timeout in seconds (default: 60)

#### Logging

- `log_level`: Logging level (options: "DEBUG", "INFO", "WARNING", "ERROR")

## Usage

### Basic Usage

```python
from code_indexer.tools.vector_store_factory import VectorStoreFactory
from code_indexer.utils.vector_store_utils import load_vector_store_config

# Load configuration
config = load_vector_store_config()

# Create vector store instance
vector_store = VectorStoreFactory.create_vector_store(config)

# Connect to Milvus
vector_store.connect()

# Create a collection for code embeddings
metadata_schema = {
    "file_path": "string",
    "language": "string",
    "entity_type": "string",
    "entity_id": "string"
}

vector_store.create_collection(
    name="code_embeddings",
    dimension=1536,  # Dimension of your embedding model
    metadata_schema=metadata_schema
)

# Insert embeddings
vector_store.insert(
    collection="code_embeddings",
    vectors=embeddings,  # List of numpy arrays or lists
    metadata=metadata    # List of metadata dictionaries
)

# Search for similar code
results = vector_store.search(
    collection="code_embeddings",
    query_vectors=[query_vector],
    top_k=10,
    filters={"language": "python"}
)

# Clean up
vector_store.disconnect()
```

### Filtering Searches

The Milvus implementation supports complex filters for narrowing search results. Use the `FilterBuilder` utility for constructing filters:

```python
from code_indexer.utils.vector_store_utils import FilterBuilder

# Find Python functions or methods in a specific repository
complex_filter = FilterBuilder.and_filter([
    FilterBuilder.exact_match("language", "python"),
    FilterBuilder.exact_match("repository", "my-repo"),
    FilterBuilder.or_filter([
        FilterBuilder.exact_match("entity_type", "function"),
        FilterBuilder.exact_match("entity_type", "method")
    ]),
    FilterBuilder.range("start_line", gte=100, lte=500)
])

# Search with filter
results = vector_store.search(
    collection="code_embeddings",
    query_vectors=[query_vector],
    top_k=10,
    filters=complex_filter
)
```

## Performance Optimization

### Index Selection

For code search applications, we recommend the following:

- For smaller codebases (< 1 million embeddings):
  - Use the `HNSW` index type for best search quality

- For larger codebases:
  - Use `IVF_FLAT` for a good balance of speed and quality
  - Increase `nlist` as your dataset grows (√n is a good rule of thumb)

### Batch Processing

For large import operations, use batch processing:

```python
# Process embeddings in batches
batch_size = 1000
for i in range(0, len(embeddings), batch_size):
    batch_vectors = embeddings[i:i+batch_size]
    batch_metadata = metadata[i:i+batch_size]
    
    vector_store.insert(
        collection="code_embeddings",
        vectors=batch_vectors,
        metadata=batch_metadata
    )
```

## Troubleshooting

### Common Issues

1. **Connection Refused**:
   - Ensure Milvus is running using `docker ps`
   - Check if the port is correctly exposed and not blocked by a firewall

2. **Memory Issues**:
   - Reduce the `batch_size` for large vector operations
   - Consider releasing collections when not in use with `collection.release()`

3. **Search Performance**:
   - Adjust search parameters based on your index type:
     - For HNSW, increase `search_ef` for better recall (but slower search)
     - For IVF, increase `search_nprobe` to search more clusters

### Logs

Enable detailed logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Examples

See the `examples/milvus_store_example.py` file for a complete example of using the Milvus vector store implementation.