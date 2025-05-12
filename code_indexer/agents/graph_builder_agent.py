"""
Graph Builder Agent

This agent builds a knowledge graph from code ASTs using Neo4j.
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional, Tuple

from google.adk import Agent, AgentContext
from google.adk.tooling import BaseTool

from code_indexer.tools.neo4j_tool import Neo4jTool
from code_indexer.utils.ast_utils import find_entity_in_ast, get_function_info, get_class_info


class GraphBuilderAgent(Agent):
    """
    Agent responsible for building and updating the code knowledge graph.
    
    This agent takes AST structures from the CodeParserAgent and creates
    a graph representation in Neo4j, capturing code entities and their relationships.
    """
    
    def __init__(self):
        """Initialize the Graph Builder Agent."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def initialize(self, context: AgentContext) -> None:
        """
        Initialize the agent with necessary tools and state.
        
        Args:
            context: The agent context
        """
        self.context = context
        
        # Initialize the Neo4j tool
        self.neo4j_tool = Neo4jTool()
        
        # Initialize state
        if "graph_stats" not in context.state:
            context.state["graph_stats"] = {
                "files": 0,
                "classes": 0,
                "functions": 0,
                "relationships": 0
            }
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build or update the code knowledge graph.
        
        Args:
            inputs: Dictionary containing parsed files with AST data
            
        Returns:
            Dictionary with graph update results
        """
        # Extract inputs
        parsed_files = inputs.get("parsed_files", [])
        deleted_files = inputs.get("deleted_files", [])
        repo_path = inputs.get("repo_path", "")
        
        if not parsed_files and not deleted_files:
            self.logger.warning("No files to process")
            return {"status": "no_files"}
        
        # Process deleted files first
        deleted_count = 0
        if deleted_files:
            deleted_count = self._process_deleted_files(deleted_files)
        
        # Process each parsed file
        file_nodes = []
        class_nodes = []
        function_nodes = []
        relationship_count = 0
        
        for file_data in parsed_files:
            file_path = file_data["path"]
            file_id = file_data["file_id"]
            language = file_data["language"]
            ast_data = file_data["ast"]
            
            try:
                # Create file node
                file_node = self.neo4j_tool.create_file_node(
                    file_id=file_id,
                    path=file_path,
                    language=language,
                    repo_path=repo_path
                )
                file_nodes.append(file_node)
                
                # Process classes
                classes = find_entity_in_ast(ast_data, "ClassDef")
                for class_ast in classes:
                    class_info = get_class_info(class_ast)
                    class_node = self.neo4j_tool.create_class_node(
                        class_id=f"{file_id}_{class_info['name']}",
                        name=class_info['name'],
                        file_id=file_id,
                        start_line=class_info['start_line'],
                        end_line=class_info['end_line'],
                        docstring=class_info['docstring']
                    )
                    class_nodes.append(class_node)
                    
                    # Create CONTAINS relationship
                    self.neo4j_tool.create_relationship(
                        from_id=file_id,
                        to_id=f"{file_id}_{class_info['name']}",
                        rel_type="CONTAINS"
                    )
                    relationship_count += 1
                    
                    # Process methods
                    for method_info in class_info['methods']:
                        method_node = self.neo4j_tool.create_function_node(
                            function_id=f"{file_id}_{class_info['name']}_{method_info['name']}",
                            name=method_info['name'],
                            file_id=file_id,
                            class_id=f"{file_id}_{class_info['name']}",
                            start_line=method_info['start_line'],
                            end_line=method_info['end_line'],
                            params=method_info['params'],
                            docstring=method_info['docstring'],
                            is_method=True
                        )
                        function_nodes.append(method_node)
                        
                        # Create CONTAINS relationship
                        self.neo4j_tool.create_relationship(
                            from_id=f"{file_id}_{class_info['name']}",
                            to_id=f"{file_id}_{class_info['name']}_{method_info['name']}",
                            rel_type="CONTAINS"
                        )
                        relationship_count += 1
                
                # Process functions (not methods)
                functions = find_entity_in_ast(ast_data, "FunctionDef")
                for func_ast in functions:
                    # Skip if it's a method (already processed)
                    is_method = False
                    for class_info in [get_class_info(c) for c in classes]:
                        if any(m['name'] == func_ast.get('name', '') for m in class_info['methods']):
                            is_method = True
                            break
                    
                    if is_method:
                        continue
                    
                    func_info = get_function_info(func_ast)
                    func_node = self.neo4j_tool.create_function_node(
                        function_id=f"{file_id}_{func_info['name']}",
                        name=func_info['name'],
                        file_id=file_id,
                        start_line=func_info['start_line'],
                        end_line=func_info['end_line'],
                        params=func_info['params'],
                        docstring=func_info['docstring'],
                        is_method=False
                    )
                    function_nodes.append(func_node)
                    
                    # Create CONTAINS relationship
                    self.neo4j_tool.create_relationship(
                        from_id=file_id,
                        to_id=f"{file_id}_{func_info['name']}",
                        rel_type="CONTAINS"
                    )
                    relationship_count += 1
                
                # Process calls
                calls = file_data.get("calls", [])
                if calls:
                    self._process_calls(file_id, calls)
                    relationship_count += len(calls)
                
                self.logger.info(f"Processed graph for {file_path}")
                
            except Exception as e:
                self.logger.error(f"Error building graph for {file_path}: {e}")
        
        # Update graph stats
        self.context.state["graph_stats"]["files"] += len(file_nodes)
        self.context.state["graph_stats"]["classes"] += len(class_nodes)
        self.context.state["graph_stats"]["functions"] += len(function_nodes)
        self.context.state["graph_stats"]["relationships"] += relationship_count
        
        # Return results
        return {
            "files_processed": len(parsed_files),
            "files_deleted": deleted_count,
            "nodes_created": len(file_nodes) + len(class_nodes) + len(function_nodes),
            "relationships_created": relationship_count,
            "graph_id": str(time.time())  # A simple graph version ID
        }
    
    def _process_deleted_files(self, deleted_files: List[str]) -> int:
        """
        Remove nodes for deleted files from the graph.
        
        Args:
            deleted_files: List of deleted file paths
            
        Returns:
            Number of files processed
        """
        count = 0
        for file_path in deleted_files:
            try:
                # Generate file ID
                import hashlib
                file_id = hashlib.md5(file_path.encode()).hexdigest()
                
                # Delete file node and all its relationships
                self.neo4j_tool.delete_file_and_contents(file_id)
                count += 1
                self.logger.info(f"Removed {file_path} from graph")
            except Exception as e:
                self.logger.error(f"Error removing {file_path} from graph: {e}")
        
        return count
    
    def _process_calls(self, file_id: str, calls: List[str]) -> None:
        """
        Process function/method calls and create CALLS relationships.
        
        Args:
            file_id: ID of the file containing the calls
            calls: List of function/method call names
        """
        for call in calls:
            try:
                # Try to find target function node
                target_nodes = self.neo4j_tool.find_function_by_name(call)
                
                if target_nodes:
                    # Create CALLS relationship from file to functions
                    for target_id in target_nodes:
                        self.neo4j_tool.create_relationship(
                            from_id=file_id,
                            to_id=target_id,
                            rel_type="CALLS"
                        )
            except Exception as e:
                self.logger.warning(f"Error processing call to {call}: {e}")