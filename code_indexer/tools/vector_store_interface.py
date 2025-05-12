"""
Vector Store Interface

Abstract base class for vector store implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
import numpy as np


class SearchResult:
    """Standardized search result across all vector stores."""
    
    def __init__(self, id: str, score: float, 
                metadata: Optional[Dict[str, Any]] = None,
                vector: Optional[List[float]] = None):
        """
        Initialize a search result.
        
        Args:
            id: Vector ID
            score: Similarity score
            metadata: Vector metadata
            vector: The vector itself (optional)
        """
        self.id = id
        self.score = score
        self.metadata = metadata or {}
        self.vector = vector
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dictionary with result data
        """
        result = {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata
        }
        
        if self.vector is not None:
            if isinstance(self.vector, np.ndarray):
                result["vector"] = self.vector.tolist()
            else:
                result["vector"] = self.vector
                
        return result


class VectorStoreInterface(ABC):
    """
    Abstract interface for vector database operations.
    
    This class defines the contract that all vector store implementations
    must follow, providing a consistent interface for embedding storage
    and retrieval.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the vector store.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Close connection to the vector store.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def collection_exists(self, name: str) -> bool:
        """
        Check if a collection exists.
        
        Args:
            name: Name of the collection
            
        Returns:
            True if collection exists, False otherwise
        """
        pass
    
    @abstractmethod
    def drop_collection(self, name: str) -> bool:
        """
        Drop a collection.
        
        Args:
            name: Name of the collection
            
        Returns:
            True if collection dropped successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def list_collections(self) -> List[str]:
        """
        List all collections.
        
        Returns:
            List of collection names
        """
        pass
    
    @abstractmethod
    def collection_stats(self, name: str) -> Dict[str, Any]:
        """
        Get statistics about a collection.
        
        Args:
            name: Name of the collection
            
        Returns:
            Dictionary with collection statistics
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get(self, collection: str, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve vectors by their IDs.
        
        Args:
            collection: Name of the collection
            ids: List of vector IDs
            
        Returns:
            List of vectors with metadata
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def count(self, collection: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count vectors in a collection.
        
        Args:
            collection: Name of the collection
            filters: Filter conditions
            
        Returns:
            Vector count
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the vector store.
        
        Returns:
            Dictionary with health information
        """
        pass