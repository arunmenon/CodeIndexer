# Milvus Integration for Code Indexer

## Overview

This document outlines the implementation approach for integrating Milvus as the preferred vector database for the Code Indexer's embedding storage and retrieval. The integration leverages the vector store abstraction layer to provide a clean implementation that can be easily configured.

## Milvus Overview

Milvus is an open-source vector database built specifically for AI applications and similarity search. It offers:

1. **High Performance**: Optimized for billion-scale vector similarity search
2. **Scalability**: Distributed architecture that scales horizontally
3. **Flexibility**: Support for multiple index types and distance metrics
4. **Rich Filtering**: Advanced filtering capabilities for hybrid searches
5. **Cloud-Native**: Kubernetes-friendly deployment options

## Implementation Details

### 1. Milvus Client Setup

```python
from pymilvus import connections, Collection, utility
from pymilvus import CollectionSchema, FieldSchema, DataType
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Union

from code_indexer.vector_store.interface import VectorStoreInterface, SearchResult

class MilvusVectorStore(VectorStoreInterface):
    """Milvus implementation of vector store interface."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.config = config
        self.connection_alias = config.get("connection_alias", "default")
        self.connected = False
        self._collections = {}  # Cache for collection objects
        
        # Configure logging
        self.logger = logging.getLogger("milvus_vector_store")
```

### 2. Connection Management

```python
def connect(self) -> bool:
    """Connect to Milvus server."""
    try:
        self.logger.info(f"Connecting to Milvus server at {self.config.get('host')}:{self.config.get('port')}")
        
        connections.connect(
            alias=self.connection_alias,
            host=self.config.get("host", "localhost"),
            port=self.config.get("port", 19530),
            user=self.config.get("user", ""),
            password=self.config.get("password", ""),
            secure=self.config.get("secure", False)
        )
        
        # Verify connection
        if utility.has_collection("_dummy_check_"):
            utility.drop_collection("_dummy_check_")
            
        self.connected = True
        self.logger.info("Successfully connected to Milvus")
        return True
    except Exception as e:
        self.logger.error(f"Failed to connect to Milvus: {e}")
        self.connected = False
        return False

def disconnect(self) -> bool:
    """Disconnect from Milvus server."""
    try:
        connections.disconnect(self.connection_alias)
        self.connected = False
        self._collections = {}
        self.logger.info("Disconnected from Milvus")
        return True
    except Exception as e:
        self.logger.error(f"Failed to disconnect from Milvus: {e}")
        return False
```

### 3. Collection Management

```python
def create_collection(self, name: str, dimension: int,
                    metadata_schema: Dict[str, str] = None,
                    distance_metric: str = "cosine") -> bool:
    """Create a new collection in Milvus."""
    try:
        # Ensure connection
        if not self.connected:
            self.connect()
        
        # Check if collection already exists
        if utility.has_collection(name):
            self.logger.info(f"Collection {name} already exists")
            return True
        
        # Define fields
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension)
        ]
        
        # Add metadata fields
        if metadata_schema:
            for field_name, field_type in metadata_schema.items():
                dtype = self._convert_type(field_type)
                if dtype == DataType.VARCHAR:
                    fields.append(FieldSchema(name=field_name, dtype=dtype, max_length=65535))
                else:
                    fields.append(FieldSchema(name=field_name, dtype=dtype))
        
        # Create schema and collection
        schema = CollectionSchema(fields=fields, description=f"Code Indexer collection - {name}")
        collection = Collection(name=name, schema=schema)
        
        # Create index on vector field
        metric_type_map = {
            "cosine": "COSINE",
            "euclidean": "L2",
            "dot": "IP",
            "l2": "L2"
        }
        metric_type = metric_type_map.get(distance_metric.lower(), "COSINE")
        
        # Get index parameters from config or use defaults
        index_type = self.config.get("index_type", "HNSW")
        index_params = self.config.get("index_params", {"M": 8, "efConstruction": 64})
        
        collection.create_index(
            field_name="vector", 
            index_type=index_type,
            metric_type=metric_type, 
            params=index_params
        )
        
        # Create scalar field indexes for faster filtering
        if metadata_schema:
            for field_name in metadata_schema:
                try:
                    collection.create_index(field_name=field_name)
                except Exception as e:
                    self.logger.warning(f"Could not create index for field {field_name}: {e}")
        
        # Cache collection
        self._collections[name] = collection
        self.logger.info(f"Created collection {name} with dimension {dimension}")
        return True
    except Exception as e:
        self.logger.error(f"Failed to create Milvus collection: {e}")
        return False
```

### 4. Vector Operations (Insert, Search, Delete)

```python
def insert(self, collection: str, vectors: List[np.ndarray], 
          metadata: List[Dict[str, Any]] = None,
          ids: List[str] = None) -> List[str]:
    """Insert vectors into a collection."""
    try:
        # Get collection
        col = self._get_collection(collection)
        if not col:
            raise ValueError(f"Collection {collection} not found")
        
        # Prepare data
        count = len(vectors)
        if metadata is None:
            metadata = [{} for _ in range(count)]
        
        # Generate IDs if not provided
        generated_ids = []
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in range(count)]
            generated_ids = ids
        
        # Convert vectors to lists
        vector_lists = [vec.tolist() for vec in vectors]
        
        # Prepare entities
        entities = [ids, vector_lists]
        
        # Add metadata fields
        for field in col.schema.fields:
            field_name = field.name
            if field_name not in ["id", "vector"]:
                field_values = []
                for i in range(count):
                    if i < len(metadata) and field_name in metadata[i]:
                        field_values.append(metadata[i][field_name])
                    else:
                        # Add default value based on field type
                        if field.dtype == DataType.VARCHAR:
                            field_values.append("")
                        elif field.dtype in [DataType.INT64, DataType.INT32, DataType.INT16, DataType.INT8]:
                            field_values.append(0)
                        elif field.dtype in [DataType.FLOAT, DataType.DOUBLE]:
                            field_values.append(0.0)
                        elif field.dtype == DataType.BOOLEAN:
                            field_values.append(False)
                        else:
                            field_values.append(None)
                entities.append(field_values)
        
        # Insert data
        insert_result = col.insert(entities)
        col.flush()  # Ensure data is flushed to storage
        
        self.logger.info(f"Inserted {count} vectors into collection {collection}")
        return generated_ids if ids == generated_ids else ids
    except Exception as e:
        self.logger.error(f"Failed to insert into Milvus: {e}")
        return []

def search(self, collection: str, query_vectors: List[np.ndarray],
          top_k: int = 10, 
          filters: Dict[str, Any] = None,
          output_fields: List[str] = None) -> List[SearchResult]:
    """Search for similar vectors in Milvus."""
    try:
        # Get collection
        col = self._get_collection(collection)
        if not col:
            raise ValueError(f"Collection {collection} not found")
        
        # Load collection if not loaded
        if not col.is_loaded:
            col.load()
        
        # Convert generic filters to Milvus expression
        expr = None
        if filters:
            expr = self._convert_filters(filters)
            self.logger.debug(f"Converted filters to expression: {expr}")
        
        # Set output fields
        output_fields = output_fields or ["*"]
        
        # Configure search parameters based on the index type
        index_params = col.index().params
        search_params = {}
        if index_params.get("index_type") == "HNSW":
            search_params = {
                "params": {"ef": self.config.get("search_ef", 64)}
            }
        elif index_params.get("index_type") == "IVF_FLAT":
            search_params = {
                "params": {"nprobe": self.config.get("search_nprobe", 10)}
            }
        else:
            # Default search params
            search_params = {
                "params": {"nprobe": 10}
            }
        
        # Add metric type
        search_params["metric_type"] = index_params.get("metric_type", "COSINE")
        
        # Convert numpy arrays to lists
        query_vectors_list = [vec.tolist() for vec in query_vectors]
        
        # Perform search
        self.logger.debug(f"Searching collection {collection} with {len(query_vectors)} vectors")
        search_results = col.search(
            data=query_vectors_list,
            anns_field="vector",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=output_fields if output_fields != ["*"] else None
        )
        
        # Convert results to standard format
        results = []
        for i, batch_results in enumerate(search_results):
            batch_search_results = []
            
            for hit in batch_results:
                # Extract metadata (all fields except id and vector)
                metadata = {}
                for field_name, field_value in hit.entity.items():
                    if field_name not in ["id", "vector"]:
                        metadata[field_name] = field_value
                
                # Create standard result object
                search_result = SearchResult(
                    id=hit.id,
                    score=hit.distance,  # Note: this is the raw distance/similarity score
                    metadata=metadata
                )
                batch_search_results.append(search_result)
            
            results.append(batch_search_results)
        
        # If only one query vector, return just its results
        self.logger.info(f"Search returned {len(results[0] if len(results) == 1 else results)} results")
        return results[0] if len(query_vectors) == 1 else results
    except Exception as e:
        self.logger.error(f"Failed to search Milvus: {e}")
        return []

def delete(self, collection: str, ids: List[str] = None, 
          filters: Dict[str, Any] = None) -> int:
    """Delete vectors by id or filters."""
    try:
        # Get collection
        col = self._get_collection(collection)
        if not col:
            raise ValueError(f"Collection {collection} not found")
        
        # Delete by IDs if provided
        if ids:
            expr = f"id in [\"{'\", \"'.join(ids)}\"]"
            result = col.delete(expr)
            delete_count = result.delete_count
        
        # Delete by filters if provided
        elif filters:
            expr = self._convert_filters(filters)
            if not expr:
                raise ValueError("Invalid filters provided")
            
            result = col.delete(expr)
            delete_count = result.delete_count
        
        # No deletion criteria provided
        else:
            raise ValueError("Either ids or filters must be provided")
        
        self.logger.info(f"Deleted {delete_count} vectors from collection {collection}")
        return delete_count
    except Exception as e:
        self.logger.error(f"Failed to delete from Milvus: {e}")
        return 0
```

### 5. Helper Methods

```python
def _get_collection(self, name: str) -> Optional[Collection]:
    """Get a collection by name, with caching."""
    if name in self._collections:
        return self._collections[name]
    
    try:
        if utility.has_collection(name):
            collection = Collection(name)
            self._collections[name] = collection
            return collection
        
        self.logger.warning(f"Collection {name} not found")
        return None
    except Exception as e:
        self.logger.error(f"Failed to get Milvus collection {name}: {e}")
        return None

def _convert_type(self, field_type: str) -> DataType:
    """Convert generic type string to Milvus DataType."""
    type_mapping = {
        "string": DataType.VARCHAR,
        "int": DataType.INT64,
        "integer": DataType.INT64,
        "float": DataType.FLOAT,
        "double": DataType.DOUBLE,
        "bool": DataType.BOOLEAN,
        "boolean": DataType.BOOLEAN,
        "array": DataType.ARRAY,
        # Add other mappings as needed
    }
    dtype = type_mapping.get(field_type.lower(), DataType.VARCHAR)
    self.logger.debug(f"Converting field type {field_type} to Milvus type {dtype}")
    return dtype

def _convert_filters(self, filters: Dict[str, Any]) -> str:
    """Convert generic filters to Milvus expression string."""
    if not filters:
        return None
    
    # Handle flat key-value filters (most common case)
    if "operator" not in filters:
        expressions = []
        for field, value in filters.items():
            if isinstance(value, str):
                expressions.append(f'{field} == "{value}"')
            elif isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
                value_list = '", "'.join(value)
                expressions.append(f'{field} in ["{value_list}"]')
            elif isinstance(value, (list, tuple)):
                value_list = ', '.join(str(v) for v in value)
                expressions.append(f'{field} in [{value_list}]')
            else:
                expressions.append(f"{field} == {value}")
        
        return " && ".join(expressions) if expressions else None
    
    # Handle structured filter with operators
    return self._build_expression(filters)

def _build_expression(self, filter_dict: Dict[str, Any]) -> str:
    """Build a Milvus filter expression from structured filter dict."""
    operator = filter_dict.get("operator", "")
    
    if operator == "==":
        field = filter_dict.get("field", "")
        value = filter_dict.get("value")
        if isinstance(value, str):
            return f'{field} == "{value}"'
        return f"{field} == {value}"
    
    elif operator == "!=":
        field = filter_dict.get("field", "")
        value = filter_dict.get("value")
        if isinstance(value, str):
            return f'{field} != "{value}"'
        return f"{field} != {value}"
    
    elif operator == "range":
        field = filter_dict.get("field", "")
        conditions = filter_dict.get("conditions", {})
        expressions = []
        
        if "gte" in conditions:
            expressions.append(f"{field} >= {conditions['gte']}")
        if "gt" in conditions:
            expressions.append(f"{field} > {conditions['gt']}")
        if "lte" in conditions:
            expressions.append(f"{field} <= {conditions['lte']}")
        if "lt" in conditions:
            expressions.append(f"{field} < {conditions['lt']}")
        
        return " && ".join(expressions)
    
    elif operator == "in":
        field = filter_dict.get("field", "")
        values = filter_dict.get("value", [])
        
        if not values:
            return ""
        
        if isinstance(values[0], str):
            value_str = '", "'.join(values)
            return f'{field} in ["{value_str}"]'
        else:
            value_str = ", ".join(str(v) for v in values)
            return f"{field} in [{value_str}]"
    
    elif operator == "and":
        conditions = filter_dict.get("conditions", [])
        expressions = []
        
        for condition in conditions:
            expr = self._build_expression(condition)
            if expr:  # Only add non-empty expressions
                expressions.append(f"({expr})")
        
        return " && ".join(expressions)
    
    elif operator == "or":
        conditions = filter_dict.get("conditions", [])
        expressions = []
        
        for condition in conditions:
            expr = self._build_expression(condition)
            if expr:  # Only add non-empty expressions
                expressions.append(f"({expr})")
        
        return " || ".join(expressions)
    
    return ""
```

### 6. Milvus Configuration Options

Here are the recommended configuration options for Milvus in the Code Indexer:

```yaml
vector_store:
  type: "milvus"
  default_collection: "code_embeddings"
  embedding_dimension: 1536
  
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
    
    # Performance tuning
    connection_pool_size: 10
    batch_size: 1000
    timeout: 60         # seconds
    
    # Logging
    log_level: "INFO"   # Options: DEBUG, INFO, WARNING, ERROR
```

### 7. Dockerfile for Milvus Deployment

To simplify deployment, here's a Docker Compose configuration for Milvus:

```yaml
# docker-compose.yml for Milvus standalone deployment
version: '3.5'

services:
  etcd:
    container_name: milvus-etcd
    image: quay.io/coreos/etcd:v3.5.0
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
      - ETCD_SNAPSHOT_COUNT=50000
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/etcd:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd

  minio:
    container_name: milvus-minio
    image: minio/minio:RELEASE.2022-03-17T06-34-49Z
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/minio:/minio_data
    command: minio server /minio_data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  standalone:
    container_name: milvus-standalone
    image: milvusdb/milvus:v2.2.11
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/milvus:/var/lib/milvus
    ports:
      - "19530:19530"
      - "9091:9091"
    depends_on:
      - "etcd"
      - "minio"

networks:
  default:
    name: milvus-network
```

### 8. Code Examples for Common Operations

#### Setup and Connection

```python
from code_indexer.vector_store import VectorStoreFactory

# Load configuration
config = {
    "type": "milvus",
    "milvus": {
        "host": "localhost",
        "port": 19530
    }
}

# Create vector store instance
vector_store = VectorStoreFactory.create_vector_store(config)

# Connect to Milvus
vector_store.connect()
```

#### Creating a Collection for Code Embeddings

```python
# Define metadata schema for code chunks
metadata_schema = {
    "file_path": "string",
    "language": "string",
    "entity_type": "string", 
    "entity_id": "string",
    "start_line": "int",
    "end_line": "int",
    "chunk_id": "string",
    "indexed_at": "string"
}

# Create collection
vector_store.create_collection(
    name="code_embeddings",
    dimension=1536,  # Matches the embedding model dimension
    metadata_schema=metadata_schema,
    distance_metric="cosine"  # Use cosine similarity for code similarity
)
```

#### Inserting Embeddings

```python
import numpy as np
from datetime import datetime

# Generate sample embeddings (in practice, these come from your embedding model)
vectors = [np.random.rand(1536).astype(np.float32) for _ in range(5)]

# Prepare metadata
metadata = [
    {
        "file_path": "/path/to/file.py",
        "language": "python",
        "entity_type": "function",
        "entity_id": "process_code",
        "start_line": 10,
        "end_line": 20,
        "chunk_id": "chunk1",
        "indexed_at": datetime.now().isoformat()
    },
    # ... more metadata entries
]

# Insert embeddings
vector_store.insert(
    collection="code_embeddings",
    vectors=vectors,
    metadata=metadata
)
```

#### Searching for Similar Code

```python
# Get query embedding (typically from embedding model)
query_vector = np.random.rand(1536).astype(np.float32)

# Simple search
results = vector_store.search(
    collection="code_embeddings",
    query_vectors=[query_vector],
    top_k=5
)

# Print results
for result in results:
    print(f"ID: {result.id}, Score: {result.score}")
    print(f"File: {result.metadata.get('file_path')}")
    print(f"Lines: {result.metadata.get('start_line')}-{result.metadata.get('end_line')}")
    print()

# Search with filters
filtered_results = vector_store.search(
    collection="code_embeddings",
    query_vectors=[query_vector],
    top_k=5,
    filters={
        "language": "python",
        "entity_type": "function"
    }
)
```

#### Advanced Filtering

```python
# Complex filter using the FilterBuilder
from code_indexer.vector_store.utils import FilterBuilder

# Find Python functions or methods that are between lines 100-200
complex_filter = FilterBuilder.and_filter([
    FilterBuilder.exact_match("language", "python"),
    FilterBuilder.or_filter([
        FilterBuilder.exact_match("entity_type", "function"),
        FilterBuilder.exact_match("entity_type", "method")
    ]),
    FilterBuilder.range("start_line", gte=100, lte=200)
])

# Search with complex filter
results = vector_store.search(
    collection="code_embeddings",
    query_vectors=[query_vector],
    top_k=10,
    filters=complex_filter
)
```

#### Deleting Embeddings

```python
# Delete by IDs
vector_store.delete(
    collection="code_embeddings",
    ids=["id1", "id2", "id3"]
)

# Delete by filters (e.g., delete all embeddings for a specific file)
vector_store.delete(
    collection="code_embeddings",
    filters={
        "file_path": "/path/to/deleted/file.py"
    }
)
```

## Performance Optimization

### 1. Index Selection

Milvus supports multiple index types. For code embeddings, the recommended choices are:

1. **HNSW** (Hierarchical Navigable Small World):
   - Best for high-recall, real-time search scenarios
   - Excellent for code search where accuracy is important
   - Parameters to tune: M (max edges), efConstruction (build quality)

2. **IVF_FLAT**:
   - Better for larger datasets with some accuracy trade-off
   - Parameters to tune: nlist (cluster count), nprobe (clusters to search)

3. **FLAT**:
   - Brute-force approach with perfect accuracy but slowest performance
   - Good for small codebases or testing

Example configuration for different index types:

```python
# HNSW Configuration
hnsw_index = {
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "params": {
        "M": 16,                # Higher values = more connections, better recall, more memory
        "efConstruction": 200,  # Higher values = better index quality, slower build time
    }
}

# IVF_FLAT Configuration
ivf_flat_index = {
    "index_type": "IVF_FLAT",
    "metric_type": "COSINE",
    "params": {
        "nlist": 1024           # Number of clusters, roughly sqrt(n) where n is collection size
    }
}
```

### 2. Batch Processing

For efficient bulk loading:

```python
def batch_ingest_embeddings(vector_store, collection, embeddings_generator, batch_size=1000):
    """Process embeddings in batches for efficient ingestion."""
    batch = []
    total_count = 0
    
    for embedding in embeddings_generator():
        batch.append(embedding)
        
        if len(batch) >= batch_size:
            # Process batch
            vectors = [item["vector"] for item in batch]
            metadata = [item["metadata"] for item in batch]
            
            vector_store.insert(
                collection=collection,
                vectors=vectors,
                metadata=metadata
            )
            
            total_count += len(batch)
            batch = []
            print(f"Processed {total_count} embeddings")
    
    # Process remaining items
    if batch:
        vectors = [item["vector"] for item in batch]
        metadata = [item["metadata"] for item in batch]
        
        vector_store.insert(
            collection=collection,
            vectors=vectors,
            metadata=metadata
        )
        
        total_count += len(batch)
    
    return total_count
```

### 3. Connection Pooling

Milvus supports connection pooling for improved performance:

```python
# Configure connection pooling in Milvus
connections.connect(
    alias="default",
    host="localhost",
    port=19530,
    pool_size=10  # Number of connections in the pool
)
```

## Production Considerations

### 1. Handling Large Collections

For very large codebases, consider:

1. **Partitioning**: Divide collections by logical units (e.g., repositories, languages)
2. **Load Management**: Load/release collections when needed to reduce memory
3. **Pagination**: When retrieving many results, use pagination

```python
# Partitioning example - create per-language collections
for language in ["python", "java", "javascript"]:
    vector_store.create_collection(
        name=f"code_embeddings_{language}",
        dimension=1536,
        metadata_schema=metadata_schema
    )

# Load/unload collections to manage memory
def search_specific_collection(vector_store, language, query_vector):
    collection_name = f"code_embeddings_{language}"
    
    # Load collection
    collection = vector_store._get_collection(collection_name)
    collection.load()
    
    # Perform search
    results = vector_store.search(
        collection=collection_name,
        query_vectors=[query_vector],
        top_k=10
    )
    
    # Release collection to free memory
    collection.release()
    
    return results
```

### 2. Monitoring and Metrics

Integrate monitoring for Milvus operations:

```python
import time
from prometheus_client import Counter, Histogram

# Define metrics
SEARCH_COUNT = Counter('milvus_search_total', 'Number of vector searches performed')
SEARCH_LATENCY = Histogram('milvus_search_latency_seconds', 'Vector search latency')
INSERT_COUNT = Counter('milvus_insert_total', 'Number of vector insertions performed')
INSERT_LATENCY = Histogram('milvus_insert_latency_seconds', 'Vector insertion latency')

# Enhance methods with metrics
def search_with_metrics(self, collection, query_vectors, top_k=10, filters=None):
    """Search with metrics tracking."""
    SEARCH_COUNT.inc()
    start_time = time.time()
    
    try:
        results = self.search(collection, query_vectors, top_k, filters)
        return results
    finally:
        SEARCH_LATENCY.observe(time.time() - start_time)

def insert_with_metrics(self, collection, vectors, metadata=None):
    """Insert with metrics tracking."""
    INSERT_COUNT.inc(len(vectors))
    start_time = time.time()
    
    try:
        ids = self.insert(collection, vectors, metadata)
        return ids
    finally:
        INSERT_LATENCY.observe(time.time() - start_time)
```

### 3. Error Handling and Retries

Implement robust error handling with retries:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def search_with_retry(vector_store, collection, query_vector, top_k=10, filters=None):
    """Search with automatic retries for transient failures."""
    try:
        return vector_store.search(collection, [query_vector], top_k, filters)
    except Exception as e:
        # Log the error
        logging.error(f"Search error: {e}")
        # Re-establish connection if needed
        if "connection" in str(e).lower():
            vector_store.disconnect()
            vector_store.connect()
        # Re-raise for retry
        raise
```

## Conclusion

This implementation provides a robust integration of Milvus as the vector database for Code Indexer. By leveraging the vector store abstraction layer, the system maintains flexibility while optimizing for Milvus's specific features and capabilities.

The approach outlined here focuses on:

1. **Clean Code Structure**: Following the abstraction design for consistent interfaces
2. **Performance Optimization**: Using Milvus-specific features for fast vector search
3. **Flexible Configuration**: Allowing tuning for different codebase sizes and requirements
4. **Robust Error Handling**: Dealing with connection issues and other failures gracefully
5. **Production Readiness**: Including monitoring, metrics, and deployment considerations

By implementing this Milvus integration, the Code Indexer will have a powerful, scalable vector storage solution that can handle large codebases while maintaining query performance.