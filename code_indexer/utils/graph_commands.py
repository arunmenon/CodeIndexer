"""
Graph Builder Command System

Implements the Command pattern for graph building operations, allowing for
transaction management, operation tracking, and potentially undoing operations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable

from code_indexer.utils.neo4j_batch import Neo4jBatchProcessor, batch_create_nodes, batch_create_relationships


class GraphCommand(ABC):
    """
    Abstract base class for graph commands.
    
    Implements the Command pattern for executing, logging, and potentially
    undoing graph operations.
    """
    
    def __init__(self):
        """Initialize the graph command."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.executed = False
        self.result = None
    
    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the command.
        
        Returns:
            Result of the operation
        """
        pass
    
    def undo(self) -> bool:
        """
        Undo the command if possible.
        
        Returns:
            True if undo was successful, False otherwise
        """
        if not self.executed:
            self.logger.warning("Cannot undo a command that hasn't been executed")
            return False
        return False
    
    def record_execution(self, result: Dict[str, Any]) -> None:
        """
        Record that the command was executed.
        
        Args:
            result: Result of the execution
        """
        self.executed = True
        self.result = result


class CreateNodesCommand(GraphCommand):
    """
    Command for creating nodes in the graph.
    """
    
    def __init__(self, neo4j_tool: Any, node_type: str, nodes: List[Dict[str, Any]], 
                config: Dict[str, Any] = None):
        """
        Initialize the create nodes command.
        
        Args:
            neo4j_tool: Neo4j tool or connector instance
            node_type: Type of node to create
            nodes: List of node data dictionaries
            config: Additional configuration
        """
        super().__init__()
        self.neo4j_tool = neo4j_tool
        self.node_type = node_type
        self.nodes = nodes
        self.config = config or {}
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the command to create nodes.
        
        Returns:
            Dictionary with operation results
        """
        result = batch_create_nodes(
            neo4j_tool=self.neo4j_tool,
            node_type=self.node_type,
            nodes=self.nodes,
            batch_size=self.config.get("batch_size", 500)
        )
        
        self.record_execution(result)
        return result
    
    def undo(self) -> bool:
        """
        Undo node creation by deleting the created nodes.
        
        Returns:
            True if undo was successful, False otherwise
        """
        if not self.executed or not self.result:
            self.logger.warning("Cannot undo: Command not executed or no result available")
            return False
            
        try:
            # Extract IDs of created nodes
            node_ids = [item.get("id") for item in self.result.get("results", [])]
            
            if not node_ids:
                self.logger.warning("No node IDs found in result to undo")
                return False
                
            # Create delete nodes command
            delete_command = DeleteNodesCommand(
                neo4j_tool=self.neo4j_tool,
                node_type=self.node_type,
                node_ids=node_ids,
                config=self.config
            )
            
            # Execute delete command
            delete_result = delete_command.execute()
            
            return delete_result.get("error_count", 0) == 0
            
        except Exception as e:
            self.logger.error(f"Error undoing node creation: {e}")
            return False


class CreateRelationshipsCommand(GraphCommand):
    """
    Command for creating relationships in the graph.
    """
    
    def __init__(self, neo4j_tool: Any, relationships: List[Dict[str, Any]],
                source_type: str = "Node", target_type: str = "Node",
                config: Dict[str, Any] = None):
        """
        Initialize the create relationships command.
        
        Args:
            neo4j_tool: Neo4j tool or connector instance
            relationships: List of relationship data dictionaries
            source_type: Type of source node
            target_type: Type of target node
            config: Additional configuration
        """
        super().__init__()
        self.neo4j_tool = neo4j_tool
        self.relationships = relationships
        self.source_type = source_type
        self.target_type = target_type
        self.config = config or {}
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the command to create relationships.
        
        Returns:
            Dictionary with operation results
        """
        result = batch_create_relationships(
            neo4j_tool=self.neo4j_tool,
            relationships=self.relationships,
            source_type=self.source_type,
            target_type=self.target_type,
            batch_size=self.config.get("batch_size", 500)
        )
        
        self.record_execution(result)
        return result


class DeleteNodesCommand(GraphCommand):
    """
    Command for deleting nodes from the graph.
    """
    
    def __init__(self, neo4j_tool: Any, node_type: str, node_ids: List[str],
                config: Dict[str, Any] = None):
        """
        Initialize the delete nodes command.
        
        Args:
            neo4j_tool: Neo4j tool or connector instance
            node_type: Type of node to delete
            node_ids: List of node IDs to delete
            config: Additional configuration
        """
        super().__init__()
        self.neo4j_tool = neo4j_tool
        self.node_type = node_type
        self.node_ids = node_ids
        self.config = config or {}
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the command to delete nodes.
        
        Returns:
            Dictionary with operation results
        """
        # Convert node IDs to expected format for batch processor
        nodes = [{"id": node_id} for node_id in self.node_ids]
        
        # Set up batch processor for delete operation
        processor_config = {
            "batch_size": self.config.get("batch_size", 500),
            "operation_type": "delete",
            "node_type": self.node_type
        }
        
        processor = Neo4jBatchProcessor(self.neo4j_tool, processor_config)
        result = processor.process(nodes)
        
        self.record_execution(result)
        return result


class GraphCommandInvoker:
    """
    Invoker for graph commands.
    
    Manages command execution, history tracking, and potentially undo operations.
    """
    
    def __init__(self):
        """Initialize the command invoker."""
        self.command_history = []
        self.undo_history = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute_command(self, command: GraphCommand) -> Dict[str, Any]:
        """
        Execute a command and add it to history.
        
        Args:
            command: The command to execute
            
        Returns:
            Result of the command execution
        """
        try:
            result = command.execute()
            self.command_history.append(command)
            return result
        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            raise
    
    def undo_last_command(self) -> bool:
        """
        Undo the last executed command.
        
        Returns:
            True if undo was successful, False otherwise
        """
        if not self.command_history:
            self.logger.warning("No commands to undo")
            return False
            
        last_command = self.command_history.pop()
        
        try:
            success = last_command.undo()
            
            if success:
                self.undo_history.append(last_command)
                return True
            else:
                # Put the command back in history if undo failed
                self.command_history.append(last_command)
                return False
                
        except Exception as e:
            # Put the command back in history if undo failed
            self.command_history.append(last_command)
            self.logger.error(f"Error undoing command: {e}")
            return False
    
    def execute_batch(self, commands: List[GraphCommand]) -> List[Dict[str, Any]]:
        """
        Execute a batch of commands.
        
        Args:
            commands: List of commands to execute
            
        Returns:
            List of command execution results
        """
        results = []
        
        for command in commands:
            try:
                result = self.execute_command(command)
                results.append(result)
            except Exception as e:
                # Log error but continue with other commands
                self.logger.error(f"Error executing command in batch: {e}")
                results.append({"error": str(e)})
                
        return results