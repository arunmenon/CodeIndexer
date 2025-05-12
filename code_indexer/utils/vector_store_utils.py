"""
Vector Store Utilities

Utilities for working with vector stores and related operations.
"""

import os
import yaml
from typing import Dict, Any, Optional, List, Union


class FilterBuilder:
    """
    Utility class for building filter expressions for vector stores.
    
    This class provides a fluent interface for constructing complex filter
    expressions in a backend-agnostic way. The resulting filters can be
    passed to vector store search methods.
    """
    
    @staticmethod
    def exact_match(field: str, value: Any) -> Dict[str, Any]:
        """
        Create an exact match filter.
        
        Args:
            field: Field name to match
            value: Value to match
            
        Returns:
            Filter dictionary
        """
        return {
            "operator": "==",
            "field": field,
            "value": value
        }
    
    @staticmethod
    def not_equal(field: str, value: Any) -> Dict[str, Any]:
        """
        Create a not-equal filter.
        
        Args:
            field: Field name to check
            value: Value to compare against
            
        Returns:
            Filter dictionary
        """
        return {
            "operator": "!=",
            "field": field,
            "value": value
        }
    
    @staticmethod
    def in_list(field: str, values: List[Any]) -> Dict[str, Any]:
        """
        Create an in-list filter.
        
        Args:
            field: Field name to check
            values: List of values to match against
            
        Returns:
            Filter dictionary
        """
        return {
            "operator": "in",
            "field": field,
            "value": values
        }
    
    @staticmethod
    def range(field: str, gt: Optional[float] = None, gte: Optional[float] = None,
             lt: Optional[float] = None, lte: Optional[float] = None) -> Dict[str, Any]:
        """
        Create a range filter.
        
        Args:
            field: Field name to filter on
            gt: Greater than value
            gte: Greater than or equal value
            lt: Less than value
            lte: Less than or equal value
            
        Returns:
            Filter dictionary
        """
        conditions = {}
        if gt is not None:
            conditions["gt"] = gt
        if gte is not None:
            conditions["gte"] = gte
        if lt is not None:
            conditions["lt"] = lt
        if lte is not None:
            conditions["lte"] = lte
            
        return {
            "operator": "range",
            "field": field,
            "conditions": conditions
        }
    
    @staticmethod
    def and_filter(conditions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create an AND filter combining multiple conditions.
        
        Args:
            conditions: List of filter conditions to combine with AND
            
        Returns:
            Filter dictionary
        """
        return {
            "operator": "and",
            "conditions": conditions
        }
    
    @staticmethod
    def or_filter(conditions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create an OR filter combining multiple conditions.
        
        Args:
            conditions: List of filter conditions to combine with OR
            
        Returns:
            Filter dictionary
        """
        return {
            "operator": "or",
            "conditions": conditions
        }


def load_vector_store_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load vector store configuration from YAML file.
    
    Args:
        config_path: Path to configuration file. If None, will look for
                    default locations.
                    
    Returns:
        Configuration dictionary
    """
    # Default config locations
    default_locations = [
        os.path.join(os.getcwd(), "config", "vector_store_config.yaml"),
        os.path.join(os.getcwd(), "code_indexer", "config", "vector_store_config.yaml"),
        os.path.join(os.path.dirname(__file__), "..", "config", "vector_store_config.yaml")
    ]
    
    # Use provided config path or try defaults
    config_locations = [config_path] if config_path else default_locations
    
    for location in config_locations:
        if location and os.path.exists(location):
            try:
                with open(location, 'r') as f:
                    config = yaml.safe_load(f)
                    if config and "vector_store" in config:
                        return config["vector_store"]
            except Exception as e:
                print(f"Error loading config from {location}: {e}")
    
    # If no config found, return default minimal config
    return {
        "type": "milvus",
        "milvus": {
            "host": "localhost",
            "port": 19530
        }
    }


def get_code_metadata_schema() -> Dict[str, str]:
    """
    Get the standard metadata schema for code embeddings.
    
    Returns:
        Dictionary mapping field names to field types
    """
    return {
        "file_path": "string",
        "language": "string",
        "entity_type": "string",
        "entity_id": "string",
        "start_line": "int",
        "end_line": "int",
        "chunk_id": "string",
        "indexed_at": "string",
        "repository": "string",
        "branch": "string",
        "commit_id": "string"
    }


def format_code_metadata(
    file_path: str,
    language: str,
    entity_type: str,
    entity_id: str,
    start_line: int,
    end_line: int,
    chunk_id: str,
    repository: Optional[str] = None,
    branch: Optional[str] = None,
    commit_id: Optional[str] = None,
    **additional_metadata
) -> Dict[str, Any]:
    """
    Format metadata for code embedding.
    
    Args:
        file_path: Path to the source file
        language: Programming language
        entity_type: Type of code entity (function, class, etc.)
        entity_id: Identifier for the code entity
        start_line: Starting line number
        end_line: Ending line number
        chunk_id: Unique identifier for the chunk
        repository: Repository identifier (optional)
        branch: Git branch (optional)
        commit_id: Git commit hash (optional)
        additional_metadata: Any additional metadata fields
        
    Returns:
        Formatted metadata dictionary
    """
    from datetime import datetime
    
    metadata = {
        "file_path": file_path,
        "language": language,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "start_line": start_line,
        "end_line": end_line,
        "chunk_id": chunk_id,
        "indexed_at": datetime.now().isoformat()
    }
    
    # Add optional fields if provided
    if repository:
        metadata["repository"] = repository
    if branch:
        metadata["branch"] = branch
    if commit_id:
        metadata["commit_id"] = commit_id
        
    # Add any additional metadata
    metadata.update(additional_metadata)
    
    return metadata