# Vector Store Abstraction Layer Design

## Overview

This document outlines a comprehensive design for the Vector Store abstraction layer in the Code Indexer system. The design follows the Adapter pattern to provide a uniform interface across different vector database implementations, with initial support for Milvus and Qdrant.

## Design Goals

1. **Interface Uniformity**: Provide a consistent API regardless of the underlying vector store
2. **Implementation Flexibility**: Allow easy switching between vector stores via configuration
3. **Performance Optimization**: Support specialized features of each backend
4. **Error Handling**: Consistent error handling across all implementations
5. **Observability**: Tracking and monitoring of vector store operations
6. **Extensibility**: Easy addition of new vector store implementations

## Architecture

The abstraction layer consists of the following components:

1. **VectorStoreInterface**: Abstract base class defining the common interface
2. **Provider Implementations**: Concrete classes for each supported vector store
3. **VectorStoreFactory**: Factory for creating appropriate implementations
4. **Configuration Management**: System for managing vector store configurations
5. **Migration Utilities**: Tools for moving data between vector stores

```
┌───────────────────┐
│  VectorStoreAgent │
└─────────┬─────────┘
          │
          │ uses
          ▼
┌───────────────────┐       ┌─────────────────┐
│ VectorStoreFactory│──────►│ Configuration   │
└─────────┬─────────┘       └─────────────────┘
          │ creates
          ▼
┌───────────────────┐
│VectorStoreInterface│
└─────────┬─────────┘
          │
          ├─────────────┬─────────────┐
          │             │             │
┌─────────▼───┐ ┌───────▼─────┐ ┌─────▼───────┐
│MilvusProvider│ │QdrantProvider│ │Other Future │
└─────────────┘ └─────────────┘ │  Providers  │
                                └─────────────┘
```

## Core Interface Definition

```python
class VectorStoreInterface(ABC):
    """Abstract interface for vector database operations."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the vector store."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to the vector store."""
        pass
    
    @abstractmethod
    def create_collection(self, name: str, dimension: int, 
                         metadata_schema: Dict[str, str] = None,
                         distance_metric: str = "cosine") -> bool:
        """Create a collection to store vectors."""
        pass
    
    @abstractmethod
    def drop_collection(self, name: str) -> bool:
        """Drop a collection."""
        pass
    
    @abstractmethod
    def list_collections(self) -> List[str]:
        """List all collections."""
        pass
    
    @abstractmethod
    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists."""
        pass
    
    @abstractmethod
    def collection_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics about a collection."""
        pass
    
    @abstractmethod
    def insert(self, collection: str, vectors: List[np.ndarray], 
              metadata: List[Dict[str, Any]] = None,
              ids: List[str] = None) -> List[str]:
        """Insert vectors into a collection."""
        pass
    
    @abstractmethod
    def batch_insert(self, collection: str, batch_size: int = 1000) -> BatchInserter:
        """Get a batch inserter for efficient bulk inserts."""
        pass
    
    @abstractmethod
    def search(self, collection: str, query_vectors: List[np.ndarray], 
              top_k: int = 10, 
              filters: Dict[str, Any] = None,
              output_fields: List[str] = None) -> List[SearchResult]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    def get(self, collection: str, ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve vectors by their ids."""
        pass
    
    @abstractmethod
    def delete(self, collection: str, ids: List[str] = None, 
              filters: Dict[str, Any] = None) -> int:
        """Delete vectors by id or filters."""
        pass
    
    @abstractmethod
    def update_metadata(self, collection: str, id: str, 
                      metadata: Dict[str, Any]) -> bool:
        """Update metadata for a vector."""
        pass
    
    @abstractmethod
    def count(self, collection: str, filters: Dict[str, Any] = None) -> int:
        """Count vectors in a collection."""
        pass
    
    @abstractmethod
    def create_index(self, collection: str, index_type: str = "hnsw",
                   index_params: Dict[str, Any] = None) -> bool:
        """Create an index on a collection."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check the health of the vector store."""
        pass
```

## Supporting Classes

```python
class SearchResult:
    """Standardized search result across all vector stores."""
    
    def __init__(self, id: str, score: float, vector: Optional[np.ndarray] = None,
                metadata: Optional[Dict[str, Any]] = None):
        self.id = id
        self.score = score
        self.vector = vector
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata
        }
        if self.vector is not None:
            result["vector"] = self.vector.tolist()
        return result


class BatchInserter:
    """Interface for batch insertion operations."""
    
    def __init__(self, vector_store, collection: str, batch_size: int):
        self.vector_store = vector_store
        self.collection = collection
        self.batch_size = batch_size
        self.vectors = []
        self.metadata = []
        self.ids = []
    
    def add(self, vector: np.ndarray, metadata: Dict[str, Any] = None,
          id: Optional[str] = None) -> None:
        """Add a vector to the batch."""
        self.vectors.append(vector)
        self.metadata.append(metadata or {})
        self.ids.append(id)
        
        if len(self.vectors) >= self.batch_size:
            self.flush()
    
    def flush(self) -> List[str]:
        """Insert accumulated vectors and clear the batch."""
        if not self.vectors:
            return []
        
        result = self.vector_store.insert(
            collection=self.collection,
            vectors=self.vectors,
            metadata=self.metadata,
            ids=self.ids
        )
        
        self.vectors = []
        self.metadata = []
        self.ids = []
        
        return result
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.flush()


class FilterBuilder:
    """Helper for building filters in a backend-agnostic way."""
    
    @staticmethod
    def exact_match(field: str, value: Any) -> Dict[str, Any]:
        return {"field": field, "operator": "==", "value": value}
    
    @staticmethod
    def range(field: str, gte: Any = None, gt: Any = None, 
            lte: Any = None, lt: Any = None) -> Dict[str, Any]:
        conditions = {}
        if gte is not None:
            conditions["gte"] = gte
        if gt is not None:
            conditions["gt"] = gt
        if lte is not None:
            conditions["lte"] = lte
        if lt is not None:
            conditions["lt"] = lt
        
        return {"field": field, "operator": "range", "conditions": conditions}
    
    @staticmethod
    def in_list(field: str, values: List[Any]) -> Dict[str, Any]:
        return {"field": field, "operator": "in", "value": values}
    
    @staticmethod
    def and_filter(filters: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"operator": "and", "conditions": filters}
    
    @staticmethod
    def or_filter(filters: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"operator": "or", "conditions": filters}
```

## Milvus Implementation

```python
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType
from pymilvus import utility

class MilvusVectorStore(VectorStoreInterface):
    """Milvus implementation of the vector store interface."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.config = config
        self.connection_alias = "default"
        self.connected = False
        self._collections = {}  # Cache for collection objects
    
    def connect(self) -> bool:
        """Connect to Milvus server."""
        try:
            connections.connect(
                alias=self.connection_alias,
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 19530),
                user=self.config.get("user", ""),
                password=self.config.get("password", ""),
                secure=self.config.get("secure", False)
            )
            self.connected = True
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Milvus: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from Milvus server."""
        try:
            connections.disconnect(self.connection_alias)
            self.connected = False
            self._collections = {}
            return True
        except Exception as e:
            logging.error(f"Failed to disconnect from Milvus: {e}")
            return False
    
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
                logging.warning(f"Collection {name} already exists")
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
            schema = CollectionSchema(fields=fields)
            collection = Collection(name=name, schema=schema)
            
            # Create index on vector field
            metric_type = "IP" if distance_metric.lower() == "dot" else "COSINE"
            index_params = {
                "metric_type": metric_type,
                "index_type": "HNSW",
                "params": {"M": 8, "efConstruction": 64}
            }
            collection.create_index(field_name="vector", index_params=index_params)
            
            # Cache collection
            self._collections[name] = collection
            return True
        except Exception as e:
            logging.error(f"Failed to create Milvus collection: {e}")
            return False
    
    def search(self, collection: str, query_vectors: List[np.ndarray],
              top_k: int = 10, 
              filters: Dict[str, Any] = None,
              output_fields: List[str] = None) -> List[SearchResult]:
        """Search for similar vectors in Milvus."""
        try:
            # Get collection
            col = self._get_collection(collection)
            if not col:
                logging.error(f"Collection {collection} not found")
                return []
            
            # Load collection if not loaded
            if not col.is_loaded:
                col.load()
            
            # Convert generic filters to Milvus expression
            expr = self._convert_filters(filters) if filters else None
            
            # Set output fields
            output_fields = output_fields or ["*"]
            
            # Set search parameters
            search_params = {
                "metric_type": "COSINE",  # Should match index metric type
                "params": {"ef": 32}  # Runtime parameter for HNSW
            }
            
            # Convert numpy arrays to lists
            query_vectors_list = [vec.tolist() for vec in query_vectors]
            
            # Perform search
            search_results = col.search(
                data=query_vectors_list,
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=output_fields
            )
            
            # Convert results to standard format
            results = []
            for batch_idx, batch_results in enumerate(search_results):
                batch_search_results = []
                
                for hit in batch_results:
                    # Extract metadata (all fields except id and vector)
                    metadata = {
                        k: v for k, v in hit.entity.items() 
                        if k not in ["id", "vector"]
                    }
                    
                    # Convert to standard result format
                    search_result = SearchResult(
                        id=hit.id,
                        score=hit.score,
                        metadata=metadata
                    )
                    batch_search_results.append(search_result)
                
                results.append(batch_search_results)
            
            # If only one query vector, return just its results
            return results[0] if len(query_vectors) == 1 else results
        except Exception as e:
            logging.error(f"Failed to search Milvus: {e}")
            return []
    
    # Additional methods...
    
    def _get_collection(self, name: str) -> Optional[Collection]:
        """Get a collection by name, with caching."""
        if name in self._collections:
            return self._collections[name]
        
        try:
            if utility.has_collection(name):
                collection = Collection(name)
                self._collections[name] = collection
                return collection
            return None
        except Exception as e:
            logging.error(f"Failed to get Milvus collection {name}: {e}")
            return None
    
    def _convert_type(self, field_type: str) -> DataType:
        """Convert generic type string to Milvus DataType."""
        type_mapping = {
            "string": DataType.VARCHAR,
            "int": DataType.INT64,
            "float": DataType.FLOAT,
            "double": DataType.DOUBLE,
            "bool": DataType.BOOLEAN,
            "array": DataType.ARRAY
        }
        return type_mapping.get(field_type.lower(), DataType.VARCHAR)
    
    def _convert_filters(self, filters: Dict[str, Any]) -> str:
        """Convert generic filters to Milvus expression string."""
        if not filters:
            return None
        
        if "operator" not in filters:
            # Assume it's a simple field=value filter
            expressions = []
            for field, value in filters.items():
                if isinstance(value, str):
                    expressions.append(f'{field} == "{value}"')
                else:
                    expressions.append(f"{field} == {value}")
            return " && ".join(expressions)
        
        return self._build_expression(filters)
    
    def _build_expression(self, filter_dict: Dict[str, Any]) -> str:
        """Build a Milvus filter expression from the filter dictionary."""
        operator = filter_dict.get("operator", "")
        
        if operator == "==":
            field = filter_dict.get("field", "")
            value = filter_dict.get("value")
            if isinstance(value, str):
                return f'{field} == "{value}"'
            return f"{field} == {value}"
        
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
            
            if isinstance(values[0], str):
                value_str = ", ".join([f'"{v}"' for v in values])
            else:
                value_str = ", ".join([str(v) for v in values])
            
            return f"{field} in [{value_str}]"
        
        elif operator == "and":
            conditions = filter_dict.get("conditions", [])
            expressions = [self._build_expression(c) for c in conditions]
            return " && ".join([f"({expr})" for expr in expressions])
        
        elif operator == "or":
            conditions = filter_dict.get("conditions", [])
            expressions = [self._build_expression(c) for c in conditions]
            return " || ".join([f"({expr})" for expr in expressions])
        
        return ""
```

## Qdrant Implementation

```python
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from qdrant_client.http.models import Filter, FieldCondition, Range, Match

class QdrantVectorStore(VectorStoreInterface):
    """Qdrant implementation of the vector store interface."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration parameters."""
        self.config = config
        self.client = None
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to Qdrant server."""
        try:
            self.client = QdrantClient(
                url=self.config.get("url", "http://localhost:6333"),
                api_key=self.config.get("api_key", None),
                timeout=self.config.get("timeout", 30.0)
            )
            # Test connection
            self.client.get_collections()
            self.connected = True
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Qdrant: {e}")
            self.connected = False
            self.client = None
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from Qdrant server."""
        self.client = None
        self.connected = False
        return True
    
    def create_collection(self, name: str, dimension: int,
                         metadata_schema: Dict[str, str] = None,
                         distance_metric: str = "cosine") -> bool:
        """Create a new collection in Qdrant."""
        try:
            # Ensure connection
            if not self.connected:
                self.connect()
            
            # Check if collection already exists
            try:
                self.client.get_collection(name)
                logging.warning(f"Collection {name} already exists")
                return True
            except:
                pass  # Collection doesn't exist, continue
            
            # Map distance metric
            distance_map = {
                "cosine": Distance.COSINE,
                "euclidean": Distance.EUCLID,
                "dot": Distance.DOT
            }
            distance = distance_map.get(distance_metric.lower(), Distance.COSINE)
            
            # Create collection
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=distance)
            )
            
            # Create payload indexes for metadata fields
            if metadata_schema:
                for field_name, field_type in metadata_schema.items():
                    self.client.create_payload_index(
                        collection_name=name,
                        field_name=field_name
                    )
            
            return True
        except Exception as e:
            logging.error(f"Failed to create Qdrant collection: {e}")
            return False
    
    def search(self, collection: str, query_vectors: List[np.ndarray],
              top_k: int = 10, 
              filters: Dict[str, Any] = None,
              output_fields: List[str] = None) -> List[SearchResult]:
        """Search for similar vectors in Qdrant."""
        try:
            # Ensure connection
            if not self.connected:
                self.connect()
            
            # Convert generic filters to Qdrant Filter
            filter_obj = self._convert_filters(filters) if filters else None
            
            # Set payload fields to retrieve
            with_payload = True
            if output_fields and output_fields != ["*"]:
                with_payload = output_fields
            
            # Perform search for each query vector
            results = []
            for query_vector in query_vectors:
                search_result = self.client.search(
                    collection_name=collection,
                    query_vector=query_vector.tolist(),
                    limit=top_k,
                    query_filter=filter_obj,
                    with_payload=with_payload
                )
                
                # Convert to standard result format
                batch_results = []
                for hit in search_result:
                    search_result = SearchResult(
                        id=hit.id,
                        score=hit.score,
                        metadata=hit.payload
                    )
                    batch_results.append(search_result)
                
                results.append(batch_results)
            
            # If only one query vector, return just its results
            return results[0] if len(query_vectors) == 1 else results
        except Exception as e:
            logging.error(f"Failed to search Qdrant: {e}")
            return []
    
    # Additional methods...
    
    def _convert_filters(self, filters: Dict[str, Any]) -> Filter:
        """Convert generic filters to Qdrant Filter object."""
        if not filters:
            return None
        
        # Simple key-value filters
        if "operator" not in filters:
            must_conditions = []
            for field, value in filters.items():
                must_conditions.append(
                    FieldCondition(
                        key=field,
                        match=Match(value=value)
                    )
                )
            return Filter(must=must_conditions)
        
        return self._build_filter(filters)
    
    def _build_filter(self, filter_dict: Dict[str, Any]) -> Filter:
        """Build a Qdrant Filter from the filter dictionary."""
        operator = filter_dict.get("operator", "")
        
        if operator == "==":
            field = filter_dict.get("field", "")
            value = filter_dict.get("value")
            return Filter(
                must=[
                    FieldCondition(
                        key=field,
                        match=Match(value=value)
                    )
                ]
            )
        
        elif operator == "range":
            field = filter_dict.get("field", "")
            conditions = filter_dict.get("conditions", {})
            range_params = {}
            
            if "gte" in conditions:
                range_params["gte"] = conditions["gte"]
            if "gt" in conditions:
                range_params["gt"] = conditions["gt"]
            if "lte" in conditions:
                range_params["lte"] = conditions["lte"]
            if "lt" in conditions:
                range_params["lt"] = conditions["lt"]
            
            return Filter(
                must=[
                    FieldCondition(
                        key=field,
                        range=Range(**range_params)
                    )
                ]
            )
        
        elif operator == "in":
            field = filter_dict.get("field", "")
            values = filter_dict.get("value", [])
            return Filter(
                must=[
                    FieldCondition(
                        key=field,
                        match=Match(any=values)
                    )
                ]
            )
        
        elif operator == "and":
            conditions = filter_dict.get("conditions", [])
            must_conditions = []
            for condition in conditions:
                sub_filter = self._build_filter(condition)
                if sub_filter.must:
                    must_conditions.extend(sub_filter.must)
            
            return Filter(must=must_conditions)
        
        elif operator == "or":
            conditions = filter_dict.get("conditions", [])
            should_conditions = []
            for condition in conditions:
                sub_filter = self._build_filter(condition)
                if sub_filter.must:
                    should_conditions.extend(sub_filter.must)
            
            return Filter(should=should_conditions)
        
        return Filter()
```

## Factory Implementation

```python
class VectorStoreFactory:
    """Factory for creating vector store instances."""
    
    @staticmethod
    def create_vector_store(config: Dict[str, Any]) -> VectorStoreInterface:
        """Create a vector store instance based on configuration."""
        store_type = config.get("type", "").lower()
        store_config = config.get(store_type, {})
        
        if store_type == "milvus":
            return MilvusVectorStore(store_config)
        elif store_type == "qdrant":
            return QdrantVectorStore(store_config)
        else:
            raise ValueError(f"Unsupported vector store type: {store_type}")
```

## Agent Integration

```python
class VectorStoreAgent(Agent):
    """Agent for interacting with vector stores."""
    
    def initialize(self, config: Dict[str, Any] = None):
        """Initialize the vector store agent."""
        # Load configuration
        self.config = config or self._load_config()
        
        # Create vector store
        self.vector_store = VectorStoreFactory.create_vector_store(self.config)
        
        # Connect to the vector store
        success = self.vector_store.connect()
        if not success:
            raise RuntimeError(f"Failed to connect to vector store")
        
        # Initialize telemetry
        self.telemetry = self._initialize_telemetry()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load vector store configuration."""
        # Implementation depends on the configuration system
        pass
    
    def _initialize_telemetry(self):
        """Initialize telemetry for monitoring vector store operations."""
        # Implementation depends on the monitoring system
        pass
    
    def create_collection(self, name: str, dimension: int = 1536,
                         metadata_schema: Dict[str, str] = None,
                         distance_metric: str = "cosine") -> bool:
        """Create a new collection."""
        start_time = time.time()
        try:
            result = self.vector_store.create_collection(
                name=name,
                dimension=dimension,
                metadata_schema=metadata_schema,
                distance_metric=distance_metric
            )
            
            # Record telemetry
            self.telemetry.record_operation(
                operation="create_collection",
                success=result,
                duration=time.time() - start_time,
                params={"name": name, "dimension": dimension}
            )
            
            return result
        except Exception as e:
            # Record error
            self.telemetry.record_operation(
                operation="create_collection",
                success=False,
                duration=time.time() - start_time,
                error=str(e),
                params={"name": name, "dimension": dimension}
            )
            raise
    
    def store_embeddings(self, collection: str, embeddings: List[Dict[str, Any]]) -> List[str]:
        """Store embeddings in the vector store.
        
        Each embedding dict should contain:
        - vector: np.ndarray
        - metadata: Dict[str, Any] (optional)
        - id: str (optional)
        """
        start_time = time.time()
        try:
            # Extract vectors, metadata, and ids
            vectors = [item["vector"] for item in embeddings]
            metadata = [item.get("metadata", {}) for item in embeddings]
            ids = [item.get("id") for item in embeddings]
            
            # Insert vectors
            result = self.vector_store.insert(
                collection=collection,
                vectors=vectors,
                metadata=metadata,
                ids=ids
            )
            
            # Record telemetry
            self.telemetry.record_operation(
                operation="store_embeddings",
                success=True,
                duration=time.time() - start_time,
                params={"collection": collection, "count": len(embeddings)}
            )
            
            return result
        except Exception as e:
            # Record error
            self.telemetry.record_operation(
                operation="store_embeddings",
                success=False,
                duration=time.time() - start_time,
                error=str(e),
                params={"collection": collection, "count": len(embeddings)}
            )
            raise
    
    def batch_store_embeddings(self, collection: str, embeddings_generator,
                             batch_size: int = 1000) -> List[str]:
        """Store embeddings from a generator in batches."""
        all_ids = []
        total_count = 0
        
        with self.vector_store.batch_insert(collection, batch_size) as inserter:
            for embedding in embeddings_generator:
                inserter.add(
                    vector=embedding["vector"],
                    metadata=embedding.get("metadata", {}),
                    id=embedding.get("id")
                )
                total_count += 1
        
        return all_ids
    
    def search(self, collection: str, query_vector: np.ndarray, top_k: int = 10,
              filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        start_time = time.time()
        try:
            results = self.vector_store.search(
                collection=collection,
                query_vectors=[query_vector],
                top_k=top_k,
                filters=filters
            )
            
            # Convert to dictionaries
            if isinstance(results, list) and all(isinstance(r, SearchResult) for r in results):
                results = [r.to_dict() for r in results]
            
            # Record telemetry
            self.telemetry.record_operation(
                operation="search",
                success=True,
                duration=time.time() - start_time,
                params={
                    "collection": collection,
                    "top_k": top_k,
                    "result_count": len(results)
                }
            )
            
            return results
        except Exception as e:
            # Record error
            self.telemetry.record_operation(
                operation="search",
                success=False,
                duration=time.time() - start_time,
                error=str(e),
                params={"collection": collection, "top_k": top_k}
            )
            raise
    
    # Additional methods...
    
    def __del__(self):
        """Cleanup when the agent is destroyed."""
        if hasattr(self, "vector_store") and self.vector_store:
            self.vector_store.disconnect()
```

## Configuration Example

```yaml
# vector_store_config.yaml
vector_store:
  type: "milvus"  # Options: "milvus", "qdrant"
  default_collection: "code_index"
  embedding_dimension: 1536
  
  # Milvus configuration
  milvus:
    host: "localhost"
    port: 19530
    user: ""
    password: ""
    secure: false
    
  # Qdrant configuration
  qdrant:
    url: "http://localhost:6333"
    api_key: ""
    timeout: 30.0
```

## Usage Examples

### Initialization:

```python
# Load configuration
config = load_yaml("config/vector_store_config.yaml")

# Create the VectorStoreAgent
vector_store_agent = VectorStoreAgent()
vector_store_agent.initialize(config["vector_store"])

# Initialize collection
metadata_schema = {
    "file_path": "string",
    "language": "string",
    "entity_type": "string",
    "entity_id": "string",
    "start_line": "int",
    "end_line": "int"
}

vector_store_agent.create_collection(
    name="code_index",
    dimension=1536,
    metadata_schema=metadata_schema
)
```

### Storing Embeddings:

```python
# Single vector insertion
vector_store_agent.store_embeddings(
    collection="code_index",
    embeddings=[
        {
            "vector": np.random.rand(1536),
            "metadata": {
                "file_path": "/path/to/file.py",
                "language": "python",
                "entity_type": "function",
                "entity_id": "my_function",
                "start_line": 10,
                "end_line": 20
            }
        }
    ]
)

# Batch insertion from generator
def embedding_generator():
    for i in range(1000):
        yield {
            "vector": np.random.rand(1536),
            "metadata": {
                "file_path": f"/path/to/file_{i}.py",
                "language": "python",
                "entity_type": "class" if i % 2 == 0 else "function",
                "entity_id": f"entity_{i}"
            }
        }

vector_store_agent.batch_store_embeddings(
    collection="code_index",
    embeddings_generator=embedding_generator(),
    batch_size=100
)
```

### Searching:

```python
# Basic search
results = vector_store_agent.search(
    collection="code_index",
    query_vector=np.random.rand(1536),
    top_k=5
)

# Search with filtering
results = vector_store_agent.search(
    collection="code_index",
    query_vector=np.random.rand(1536),
    top_k=10,
    filters={
        "language": "python",
        "entity_type": "function"
    }
)

# Advanced filtering
filters = FilterBuilder.and_filter([
    FilterBuilder.exact_match("language", "python"),
    FilterBuilder.in_list("entity_type", ["function", "method"]),
    FilterBuilder.range("start_line", gte=10, lte=100)
])

results = vector_store_agent.search(
    collection="code_index",
    query_vector=np.random.rand(1536),
    top_k=10,
    filters=filters
)
```

## Migration Between Vector Stores

```python
class VectorStoreMigration:
    """Utility for migrating between vector stores."""
    
    def __init__(self, source_config: Dict[str, Any], target_config: Dict[str, Any]):
        """Initialize migration utility."""
        self.source_store = VectorStoreFactory.create_vector_store(source_config)
        self.target_store = VectorStoreFactory.create_vector_store(target_config)
        
        self.source_store.connect()
        self.target_store.connect()
    
    def migrate_collection(self, source_collection: str, target_collection: str,
                          batch_size: int = 1000, 
                          copy_schema: bool = True) -> bool:
        """Migrate data from source to target collection."""
        try:
            # Get source collection info
            collection_stats = self.source_store.collection_stats(source_collection)
            dimension = collection_stats.get("dimension", 1536)
            count = collection_stats.get("count", 0)
            
            logging.info(f"Migrating {count} vectors from {source_collection} to {target_collection}")
            
            # Create target collection
            if copy_schema:
                # Get schema from stats if available
                metadata_schema = collection_stats.get("metadata_schema", {})
                
                self.target_store.create_collection(
                    name=target_collection,
                    dimension=dimension,
                    metadata_schema=metadata_schema
                )
            
            # Migrate in batches
            processed = 0
            batch_count = (count + batch_size - 1) // batch_size  # Ceiling division
            
            for batch_idx in range(batch_count):
                offset = batch_idx * batch_size
                
                # Get vectors from source
                results = self.source_store.get_by_bulk(
                    collection=source_collection,
                    offset=offset,
                    limit=batch_size,
                    with_vectors=True
                )
                
                # Extract vectors, metadata, and ids
                vectors = [r["vector"] for r in results]
                metadata = [r["metadata"] for r in results]
                ids = [r["id"] for r in results]
                
                # Insert into target
                self.target_store.insert(
                    collection=target_collection,
                    vectors=vectors,
                    metadata=metadata,
                    ids=ids
                )
                
                processed += len(vectors)
                logging.info(f"Migrated {processed}/{count} vectors")
            
            return True
        except Exception as e:
            logging.error(f"Migration failed: {e}")
            return False
    
    def close(self):
        """Close connections."""
        self.source_store.disconnect()
        self.target_store.disconnect()
```

## Unit Testing

Here's an example of how to test the abstraction:

```python
import unittest
import numpy as np
from unittest.mock import MagicMock, patch

class TestVectorStoreAbstraction(unittest.TestCase):
    
    def setUp(self):
        # Setup mock config
        self.mock_config = {
            "type": "milvus",
            "milvus": {
                "host": "localhost",
                "port": 19530
            }
        }
    
    @patch("vector_store.MilvusVectorStore.connect")
    def test_factory_creates_correct_implementation(self, mock_connect):
        # Arrange
        mock_connect.return_value = True
        
        # Act
        store = VectorStoreFactory.create_vector_store(self.mock_config)
        
        # Assert
        self.assertIsInstance(store, MilvusVectorStore)
        self.assertEqual(store.config, self.mock_config["milvus"])
    
    @patch("vector_store.MilvusVectorStore")
    def test_agent_initializes_store(self, MockMilvusStore):
        # Arrange
        mock_store = MagicMock()
        MockMilvusStore.return_value = mock_store
        mock_store.connect.return_value = True
        
        # Act
        agent = VectorStoreAgent()
        agent.initialize(self.mock_config)
        
        # Assert
        MockMilvusStore.assert_called_once_with(self.mock_config["milvus"])
        mock_store.connect.assert_called_once()
    
    @patch("vector_store.MilvusVectorStore")
    def test_search_functionality(self, MockMilvusStore):
        # Arrange
        mock_store = MagicMock()
        MockMilvusStore.return_value = mock_store
        mock_store.connect.return_value = True
        
        test_results = [SearchResult(id="1", score=0.9, metadata={"field": "value"})]
        mock_store.search.return_value = test_results
        
        # Act
        agent = VectorStoreAgent()
        agent.initialize(self.mock_config)
        results = agent.search(
            collection="test",
            query_vector=np.random.rand(1536),
            top_k=10
        )
        
        # Assert
        mock_store.search.assert_called_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "1")
        self.assertEqual(results[0]["score"], 0.9)
        self.assertEqual(results[0]["metadata"]["field"], "value")
```

## Conclusion

This comprehensive abstraction layer provides a uniform interface for working with different vector stores in the Code Indexer system. The design follows best practices:

1. **Clean Separation of Concerns**:
   - Interface defines the contract
   - Implementations handle backend-specific details
   - Factory provides instantiation logic
   - Agent provides high-level operations

2. **Extensibility**:
   - New vector stores can be added by implementing the interface
   - New operations can be added to the interface and implementations

3. **Error Handling and Observability**:
   - Consistent error handling across implementations
   - Telemetry for monitoring and debugging

4. **Configuration-Driven**:
   - Vector store selection and settings via configuration
   - No hard-coded dependencies

5. **Migration Support**:
   - Utility for moving data between vector stores
   - Batch processing for efficiency

By implementing this abstraction, the Code Indexer can easily switch between Milvus and Qdrant, or adopt other vector stores in the future with minimal changes to the codebase.