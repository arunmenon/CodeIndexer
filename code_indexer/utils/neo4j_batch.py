"""
Neo4j Batch Processor

Specialized batch processing utilities for Neo4j database operations.
Implements efficient batch operations for graph database transactions.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union, Tuple

from code_indexer.utils.batch_processor import BatchProcessor, BatchProcessorFactory


class Neo4jBatchProcessor(BatchProcessor[Dict[str, Any], Dict[str, Any]]):
    """
    Specialized batch processor for Neo4j operations.
    
    Optimizes Neo4j operations by using efficient batching patterns and
    parameterized Cypher queries with UNWIND for bulk operations.
    """
    
    def __init__(self, neo4j_tool: Any, config: Dict[str, Any] = None):
        """
        Initialize the Neo4j batch processor.
        
        Args:
            neo4j_tool: Instance of a Neo4j tool or connector
            config: Configuration dictionary
        """
        super().__init__(config)
        self.neo4j_tool = neo4j_tool
        self.batch_size = self.config.get("batch_size", 500)  # Neo4j-specific batch size
        self.operation_type = self.config.get("operation_type", "create")
        self.node_type = self.config.get("node_type", "Node")
        self.id_field = self.config.get("id_field", "id")
        
    def process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of Neo4j operations.
        
        Args:
            batch: List of data dictionaries to process
            
        Returns:
            List of operation results
        """
        operation_method = getattr(self, f"_batch_{self.operation_type}")
        return operation_method(batch)
    
    def _batch_create(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Perform batch creation of nodes.
        
        Args:
            items: List of node data dictionaries
            
        Returns:
            List of created node results
        """
        # Prepare data for UNWIND operation
        batch_data = []
        for item in items:
            # Extract ID and properties separately
            item_id = item.get(self.id_field) 
            if not item_id:
                self.logger.warning(f"Skipping item without ID: {item}")
                continue
                
            # Remove ID from properties
            properties = {k: v for k, v in item.items() if k != self.id_field}
            
            batch_data.append({
                "id": item_id,
                "properties": properties
            })
        
        # Execute batch create operation
        query = f"""
        UNWIND $nodes AS node
        MERGE (n:{self.node_type} {{{self.id_field}: node.id}})
        SET n += node.properties
        RETURN n.{self.id_field} as id
        """
        
        result = self.neo4j_tool.execute_cypher(query, {"nodes": batch_data})
        
        # Return created node IDs
        created_nodes = []
        for record in result:
            created_nodes.append({"id": record["id"]})
            
        return created_nodes
    
    def _batch_update(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Perform batch update of nodes.
        
        Args:
            items: List of node data dictionaries
            
        Returns:
            List of updated node results
        """
        # Prepare data for UNWIND operation
        batch_data = []
        for item in items:
            # Extract ID and properties separately
            item_id = item.get(self.id_field)
            if not item_id:
                self.logger.warning(f"Skipping item without ID: {item}")
                continue
                
            # Remove ID from properties
            properties = {k: v for k, v in item.items() if k != self.id_field}
            
            batch_data.append({
                "id": item_id,
                "properties": properties
            })
        
        # Execute batch update operation
        query = f"""
        UNWIND $nodes AS node
        MATCH (n:{self.node_type} {{{self.id_field}: node.id}})
        SET n += node.properties
        RETURN n.{self.id_field} as id
        """
        
        result = self.neo4j_tool.execute_cypher(query, {"nodes": batch_data})
        
        # Return updated node IDs
        updated_nodes = []
        for record in result:
            updated_nodes.append({"id": record["id"]})
            
        return updated_nodes
    
    def _batch_delete(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Perform batch deletion of nodes.
        
        Args:
            items: List of node data dictionaries with IDs
            
        Returns:
            List of deletion results
        """
        # Extract IDs for deletion
        ids = []
        for item in items:
            item_id = item.get(self.id_field)
            if not item_id:
                self.logger.warning(f"Skipping item without ID: {item}")
                continue
            ids.append(item_id)
        
        # Execute batch delete operation
        query = f"""
        UNWIND $ids AS id
        MATCH (n:{self.node_type} {{{self.id_field}: id}})
        DETACH DELETE n
        RETURN id
        """
        
        result = self.neo4j_tool.execute_cypher(query, {"ids": ids})
        
        # Return deleted node IDs
        deleted_nodes = []
        for record in result:
            deleted_nodes.append({"id": record["id"]})
            
        return deleted_nodes
    
    def _batch_create_relationships(self, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Perform batch creation of relationships.
        
        Args:
            relationships: List of relationship data dictionaries
            
        Returns:
            List of created relationship results
        """
        # relationship format: {source_id, target_id, type, properties}
        batch_data = []
        for rel in relationships:
            source_id = rel.get("source_id")
            target_id = rel.get("target_id")
            rel_type = rel.get("type", "RELATED_TO")
            
            if not source_id or not target_id:
                self.logger.warning(f"Skipping relationship without source or target ID: {rel}")
                continue
                
            # Extract properties
            properties = {k: v for k, v in rel.items() 
                         if k not in ["source_id", "target_id", "type"]}
            
            batch_data.append({
                "source_id": source_id,
                "target_id": target_id,
                "type": rel_type,
                "properties": properties
            })
        
        # Execute batch relationship creation
        source_type = self.config.get("source_type", "Node")
        target_type = self.config.get("target_type", "Node")
        
        query = f"""
        UNWIND $relationships AS rel
        MATCH (source:{source_type} {{{self.id_field}: rel.source_id}})
        MATCH (target:{target_type} {{{self.id_field}: rel.target_id}})
        MERGE (source)-[r:{self.config.get("relationship_placeholder", "$TYPE")}]->(target)
        SET r += rel.properties
        RETURN id(r) as id, rel.source_id as source_id, rel.target_id as target_id
        """
        
        # Replace relationship placeholder with actual value
        # This approach allows dynamically setting the relationship type for each relationship
        if "$TYPE" in query:
            # Use a batch of queries, one for each relationship type
            rel_types = set(rel["type"] for rel in batch_data)
            all_results = []
            
            for rel_type in rel_types:
                # Filter relationships of this type
                type_rels = [rel for rel in batch_data if rel["type"] == rel_type]
                type_query = query.replace("$TYPE", rel_type)
                type_result = self.neo4j_tool.execute_cypher(type_query, {"relationships": type_rels})
                
                # Collect results
                for record in type_result:
                    all_results.append({
                        "id": record["id"],
                        "source_id": record["source_id"],
                        "target_id": record["target_id"]
                    })
            
            return all_results
        else:
            # All relationships have the same type
            result = self.neo4j_tool.execute_cypher(query, {"relationships": batch_data})
            
            # Return created relationship IDs
            created_rels = []
            for record in result:
                created_rels.append({
                    "id": record["id"],
                    "source_id": record["source_id"],
                    "target_id": record["target_id"]
                })
                
            return created_rels


class Neo4jBatchCommand:
    """
    Command pattern implementation for Neo4j batch operations.
    
    Encapsulates Neo4j operations as command objects that can be executed,
    tracked, and potentially undone.
    """
    
    def __init__(self, neo4j_tool: Any, operation: str, node_type: str, 
                 data: List[Dict[str, Any]], config: Dict[str, Any] = None):
        """
        Initialize the Neo4j batch command.
        
        Args:
            neo4j_tool: Instance of a Neo4j tool or connector
            operation: Type of operation ("create", "update", "delete", "create_relationships")
            node_type: Type of node to operate on
            data: Data for the operation
            config: Additional configuration
        """
        self.neo4j_tool = neo4j_tool
        self.operation = operation
        self.node_type = node_type
        self.data = data
        self.config = config or {}
        self.result = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the batch command.
        
        Returns:
            Result of the operation
        """
        processor_config = {
            "batch_size": self.config.get("batch_size", 500),
            "operation_type": self.operation,
            "node_type": self.node_type,
            "id_field": self.config.get("id_field", "id"),
            **self.config
        }
        
        processor = Neo4jBatchProcessor(self.neo4j_tool, processor_config)
        result = processor.process(self.data)
        self.result = result
        return result
    
    def undo(self) -> bool:
        """
        Undo the batch operation if possible.
        
        Returns:
            True if undo was successful, False otherwise
        """
        if not self.result:
            self.logger.warning("Cannot undo operation that hasn't been executed")
            return False
            
        try:
            if self.operation == "create":
                # Delete created nodes
                created_ids = [item["id"] for item in self.result.get("results", [])]
                delete_command = Neo4jBatchCommand(
                    self.neo4j_tool, 
                    "delete", 
                    self.node_type, 
                    [{"id": id} for id in created_ids],
                    self.config
                )
                delete_command.execute()
                return True
                
            elif self.operation == "create_relationships":
                # We'd need the relationship IDs for this, which would require a different approach
                self.logger.warning("Undo for relationship creation not implemented")
                return False
                
            else:
                self.logger.warning(f"Undo not implemented for operation: {self.operation}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error undoing batch operation: {e}")
            return False


# Helper functions for common Neo4j batch operations

def batch_create_nodes(neo4j_tool: Any, node_type: str, nodes: List[Dict[str, Any]], 
                       batch_size: int = 500, **config) -> Dict[str, Any]:
    """
    Create nodes in Neo4j using efficient batching.
    
    Args:
        neo4j_tool: Neo4j tool or connector instance
        node_type: Type of node to create
        nodes: List of node data dictionaries
        batch_size: Size of each batch
        **config: Additional configuration
        
    Returns:
        Dictionary with operation results
    """
    command = Neo4jBatchCommand(
        neo4j_tool=neo4j_tool,
        operation="create",
        node_type=node_type,
        data=nodes,
        config={"batch_size": batch_size, **config}
    )
    return command.execute()


def batch_create_relationships(neo4j_tool: Any, relationships: List[Dict[str, Any]],
                              source_type: str = "Node", target_type: str = "Node",
                              batch_size: int = 500, **config) -> Dict[str, Any]:
    """
    Create relationships in Neo4j using efficient batching.
    
    Args:
        neo4j_tool: Neo4j tool or connector instance
        relationships: List of relationship data dictionaries
        source_type: Type of source node
        target_type: Type of target node
        batch_size: Size of each batch
        **config: Additional configuration
        
    Returns:
        Dictionary with operation results
    """
    command = Neo4jBatchCommand(
        neo4j_tool=neo4j_tool,
        operation="create_relationships",
        node_type="Relationship",  # Not used directly
        data=relationships,
        config={
            "batch_size": batch_size,
            "source_type": source_type,
            "target_type": target_type,
            **config
        }
    )
    return command.execute()