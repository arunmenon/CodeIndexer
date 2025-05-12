"""
Milvus Vector Store Implementation

Implementation of the vector store interface for Milvus.
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Union

import numpy as np

from code_indexer.tools.vector_store_interface import VectorStoreInterface, SearchResult

# Import pymilvus conditionally to handle missing dependencies
try:
    from pymilvus import connections, Collection, utility
    from pymilvus import CollectionSchema, FieldSchema, DataType
    HAS_MILVUS = True
except ImportError:
    HAS_MILVUS = False
    logging.warning("Milvus support not available. Install pymilvus package to enable it.")


class MilvusVectorStore(VectorStoreInterface):
    """
    Milvus implementation of vector store interface.
    
    This class provides an implementation of the VectorStoreInterface
    for the Milvus vector database.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize with configuration parameters.
        
        Args:
            config: Dictionary with Milvus configuration parameters
        """
        if not HAS_MILVUS:
            raise ImportError("Milvus support requires pymilvus package")
            
        self.config = config
        self.connection_alias = config.get("connection_alias", "default")
        self.connected = False
        self._collections = {}  # Cache for collection objects
        
        # Configure logging
        self.logger = logging.getLogger("milvus_vector_store")
        log_level = config.get("log_level", "INFO").upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    def connect(self) -> bool:
        """
        Establish connection to the Milvus server.
        
        Returns:
            True if connection successful, False otherwise
        """
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
        """
        Close connection to the Milvus server.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            connections.disconnect(self.connection_alias)
            self.connected = False
            self._collections = {}
            self.logger.info("Disconnected from Milvus")
            return True
        except Exception as e:
            self.logger.error(f"Failed to disconnect from Milvus: {e}")
            return False
    
    def create_collection(self, name: str, dimension: int, 
                         metadata_schema: Optional[Dict[str, str]] = None,
                         distance_metric: str = "cosine") -> bool:
        """
        Create a new collection to store vectors.
        
        Args:
            name: Name of the collection
            dimension: Vector dimension
            metadata_schema: Schema for vector metadata
            distance_metric: Distance metric for similarity (default: cosine)
            
        Returns:
            True if collection created successfully, False otherwise
        """
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
    
    def collection_exists(self, name: str) -> bool:
        """
        Check if a collection exists.
        
        Args:
            name: Name of the collection
            
        Returns:
            True if collection exists, False otherwise
        """
        try:
            if not self.connected:
                self.connect()
            return utility.has_collection(name)
        except Exception as e:
            self.logger.error(f"Error checking if collection exists: {e}")
            return False
    
    def drop_collection(self, name: str) -> bool:
        """
        Drop a collection.
        
        Args:
            name: Name of the collection
            
        Returns:
            True if collection dropped successfully, False otherwise
        """
        try:
            if not self.connected:
                self.connect()
                
            if utility.has_collection(name):
                utility.drop_collection(name)
                if name in self._collections:
                    del self._collections[name]
                    
                self.logger.info(f"Dropped collection {name}")
                return True
            else:
                self.logger.warning(f"Collection {name} does not exist")
                return False
        except Exception as e:
            self.logger.error(f"Failed to drop collection: {e}")
            return False
    
    def list_collections(self) -> List[str]:
        """
        List all collections.
        
        Returns:
            List of collection names
        """
        try:
            if not self.connected:
                self.connect()
                
            collections = utility.list_collections()
            self.logger.debug(f"Found {len(collections)} collections")
            return collections
        except Exception as e:
            self.logger.error(f"Failed to list collections: {e}")
            return []
    
    def collection_stats(self, name: str) -> Dict[str, Any]:
        """
        Get statistics about a collection.
        
        Args:
            name: Name of the collection
            
        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self._get_collection(name)
            if not collection:
                return {"error": f"Collection {name} not found"}
            
            stats = {
                "name": name,
                "exists": True
            }
            
            # Get entity count
            stats["row_count"] = collection.num_entities
            
            # Get schema information
            stats["schema"] = {
                "fields": [field.name for field in collection.schema.fields],
                "primary_field": next((field.name for field in collection.schema.fields 
                                     if field.is_primary), None)
            }
            
            # Get index information
            try:
                stats["index_info"] = collection.index().params
            except Exception:
                stats["index_info"] = {}
            
            return stats
        except Exception as e:
            self.logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}
    
    def insert(self, collection: str, vectors: List[Union[List[float], np.ndarray]],
              metadata: Optional[List[Dict[str, Any]]] = None,
              ids: Optional[List[str]] = None) -> List[str]:
        """
        Insert vectors into a collection.
        
        Args:
            collection: Name of the collection
            vectors: List of vectors to insert
            metadata: List of metadata dictionaries
            ids: List of vector IDs
            
        Returns:
            List of inserted vector IDs
        """
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
                ids = [str(uuid.uuid4()) for _ in range(count)]
                generated_ids = ids
            
            # Convert vectors to lists if they're numpy arrays
            vector_lists = []
            for vec in vectors:
                if isinstance(vec, np.ndarray):
                    vector_lists.append(vec.tolist())
                else:
                    vector_lists.append(vec)
            
            # Prepare entities
            entities = {"id": ids, "vector": vector_lists}
            
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
                    entities[field_name] = field_values
            
            # Insert data
            insert_result = col.insert(entities)
            col.flush()  # Ensure data is flushed to storage
            
            self.logger.info(f"Inserted {count} vectors into collection {collection}")
            return generated_ids if ids == generated_ids else ids
        except Exception as e:
            self.logger.error(f"Failed to insert into Milvus: {e}")
            return []
    
    def search(self, collection: str, query_vectors: List[Union[List[float], np.ndarray]],
              top_k: int = 10, filters: Optional[Dict[str, Any]] = None,
              output_fields: Optional[List[str]] = None) -> Union[List[SearchResult], List[List[SearchResult]]]:
        """
        Search for similar vectors.
        
        Args:
            collection: Name of the collection
            query_vectors: List of query vectors
            top_k: Number of results to return
            filters: Filter conditions for metadata
            output_fields: Metadata fields to include in results
            
        Returns:
            List of search results (or list of lists if multiple query vectors)
        """
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
            output_fields = output_fields or []
            
            # Configure search parameters based on the index type
            index_info = col.index()
            index_type = index_info.params.get("index_type", "HNSW")
            search_params = {}
            
            if index_type == "HNSW":
                search_params = {
                    "params": {"ef": self.config.get("search_ef", 64)}
                }
            elif index_type == "IVF_FLAT":
                search_params = {
                    "params": {"nprobe": self.config.get("search_nprobe", 10)}
                }
            else:
                # Default search params
                search_params = {
                    "params": {"nprobe": 10}
                }
            
            # Convert numpy arrays to lists
            query_vectors_list = []
            for vec in query_vectors:
                if isinstance(vec, np.ndarray):
                    query_vectors_list.append(vec.tolist())
                else:
                    query_vectors_list.append(vec)
            
            # Perform search
            self.logger.debug(f"Searching collection {collection} with {len(query_vectors)} vectors")
            search_results = col.search(
                data=query_vectors_list,
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=output_fields if output_fields else None
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
    
    def get(self, collection: str, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve vectors by their IDs.
        
        Args:
            collection: Name of the collection
            ids: List of vector IDs
            
        Returns:
            List of vectors with metadata
        """
        try:
            # Get collection
            col = self._get_collection(collection)
            if not col:
                raise ValueError(f"Collection {collection} not found")
            
            # Build query expression
            expr = f"id in [\"{'\", \"'.join(ids)}\"]"
            
            # Execute query
            results = col.query(
                expr=expr,
                output_fields=["*"]
            )
            
            # Format results
            formatted_results = []
            for result in results:
                vector_data = {
                    "id": result["id"],
                    "vector": result["vector"],
                    "metadata": {}
                }
                
                # Extract metadata fields
                for field_name, field_value in result.items():
                    if field_name not in ["id", "vector"]:
                        vector_data["metadata"][field_name] = field_value
                
                formatted_results.append(vector_data)
            
            self.logger.info(f"Retrieved {len(formatted_results)} vectors from collection {collection}")
            return formatted_results
        except Exception as e:
            self.logger.error(f"Failed to get vectors from Milvus: {e}")
            return []
    
    def delete(self, collection: str, ids: Optional[List[str]] = None,
              filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Delete vectors by ID or filters.
        
        Args:
            collection: Name of the collection
            ids: List of vector IDs to delete
            filters: Filter conditions for vectors to delete
            
        Returns:
            Number of vectors deleted
        """
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
    
    def count(self, collection: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count vectors in a collection.
        
        Args:
            collection: Name of the collection
            filters: Filter conditions
            
        Returns:
            Vector count
        """
        try:
            # Get collection
            col = self._get_collection(collection)
            if not col:
                raise ValueError(f"Collection {collection} not found")
            
            # Count with filters if provided
            if filters:
                expr = self._convert_filters(filters)
                if expr:
                    count = col.query(expr=expr, output_fields=["count(*)"])
                    return count[0]["count(*)"] if count else 0
            
            # Get total count
            count = col.num_entities
            return count
        except Exception as e:
            self.logger.error(f"Failed to count vectors in Milvus: {e}")
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the vector store.
        
        Returns:
            Dictionary with health information
        """
        health_info = {
            "status": "unknown",
            "connection": False,
            "collections": [],
            "server_info": {}
        }
        
        try:
            # Check connection
            if not self.connected:
                if not self.connect():
                    health_info["status"] = "error"
                    health_info["message"] = "Cannot connect to Milvus server"
                    return health_info
            
            health_info["connection"] = True
            
            # List collections
            collections = utility.list_collections()
            health_info["collections"] = collections
            
            # Get basic info about each collection
            collection_info = {}
            for name in collections:
                try:
                    collection = Collection(name)
                    collection_info[name] = {
                        "row_count": collection.num_entities,
                        "loaded": collection.is_loaded
                    }
                except Exception as e:
                    collection_info[name] = {"error": str(e)}
            
            health_info["collection_info"] = collection_info
            
            # Overall status
            health_info["status"] = "healthy"
            return health_info
        except Exception as e:
            health_info["status"] = "error"
            health_info["message"] = str(e)
            return health_info
    
    # Helper methods
    
    def _get_collection(self, name: str) -> Optional[Collection]:
        """
        Get a collection by name, with caching.
        
        Args:
            name: Collection name
            
        Returns:
            Collection object or None if not found
        """
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
        """
        Convert generic type string to Milvus DataType.
        
        Args:
            field_type: Type string (e.g., "string", "int", "float")
            
        Returns:
            Milvus DataType enum value
        """
        type_mapping = {
            "string": DataType.VARCHAR,
            "int": DataType.INT64,
            "integer": DataType.INT64,
            "float": DataType.FLOAT,
            "double": DataType.DOUBLE,
            "bool": DataType.BOOLEAN,
            "boolean": DataType.BOOLEAN,
        }
        dtype = type_mapping.get(field_type.lower(), DataType.VARCHAR)
        self.logger.debug(f"Converting field type {field_type} to Milvus type {dtype}")
        return dtype
    
    def _convert_filters(self, filters: Dict[str, Any]) -> Optional[str]:
        """
        Convert generic filters to Milvus expression string.
        
        Args:
            filters: Filter dictionary
            
        Returns:
            Milvus expression string
        """
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
        """
        Build a Milvus filter expression from structured filter dict.
        
        Args:
            filter_dict: Filter dictionary with operator and conditions
            
        Returns:
            Milvus expression string
        """
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