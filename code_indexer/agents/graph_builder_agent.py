"""
Graph Builder Agent

This agent builds a knowledge graph from code ASTs using Neo4j.
"""

import os
import logging
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union

from google.adk import Agent
from google.adk.tools.google_api_tool import AgentContext, HandlerResponse
from google.adk.tools.google_api_tool import ToolResponse, ToolStatus

from code_indexer.tools.neo4j_tool import Neo4jTool
from code_indexer.utils.ast_utils import find_entity_in_ast, get_function_info, get_class_info


class GraphBuilderAgent(Agent):
    """
    Agent responsible for building and updating the code knowledge graph.
    
    This agent takes AST structures from the CodeParserAgent and creates
    a graph representation in Neo4j, capturing code entities and their relationships.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Graph Builder Agent.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self.logger = logging.getLogger("graph_builder_agent")
        
        # Configure defaults
        self.use_imports = config.get("use_imports", True)
        self.use_inheritance = config.get("use_inheritance", True)
        self.detect_calls = config.get("detect_calls", True)
        
        # State
        self.neo4j_tool = None
        self.graph_stats = {
            "files": 0,
            "classes": 0,
            "functions": 0,
            "relationships": 0
        }
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        self.context = context
        
        # Get Neo4j tool
        tool_response = context.get_tool("neo4j_tool")
        if tool_response.status.is_success():
            self.neo4j_tool = tool_response.tool
            self.logger.info("Successfully acquired Neo4j tool")
        else:
            self.logger.error("Failed to acquire Neo4j tool: %s", 
                             tool_response.status.message)
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Build or update the code knowledge graph.
        
        Args:
            input_data: Dictionary containing code ASTs and metadata
            
        Returns:
            HandlerResponse with graph update results
        """
        self.logger.info("Starting graph builder agent")
        
        # Check if Neo4j tool is available
        if not self.neo4j_tool:
            return HandlerResponse.error("Neo4j tool not available")
        
        # Extract input data
        asts = input_data.get("asts", [])
        repository = input_data.get("repository", "")
        repository_url = input_data.get("repository_url", "")
        commit = input_data.get("commit", "")
        branch = input_data.get("branch", "")
        is_full_indexing = input_data.get("is_full_indexing", False)
        deleted_files = input_data.get("deleted_files", [])
        
        if not asts and not deleted_files:
            self.logger.warning("No data to process")
            return HandlerResponse.success({"status": "no_data"})
        
        # Process deleted files first
        deleted_count = 0
        if deleted_files:
            deleted_count = self._process_deleted_files(deleted_files)
        
        # Process each AST
        file_nodes = []
        class_nodes = []
        function_nodes = []
        relationship_count = 0
        failed_files = []
        
        for ast_data in asts:
            file_path = ast_data.get("file_path", "")
            language = ast_data.get("language", "unknown")
            
            if not file_path:
                self.logger.warning("Skipping AST with missing file path")
                continue
            
            try:
                # Generate unique file ID
                file_id = hashlib.md5(file_path.encode()).hexdigest()
                
                # Process AST into graph
                result = self._process_ast(
                    ast_data=ast_data,
                    file_id=file_id,
                    file_path=file_path,
                    language=language,
                    repository=repository,
                    repository_url=repository_url
                )
                
                # Update tracking
                file_nodes.append(file_id)
                class_nodes.extend(result.get("class_nodes", []))
                function_nodes.extend(result.get("function_nodes", []))
                relationship_count += result.get("relationship_count", 0)
                
                self.logger.info(f"Processed graph for {file_path}")
                
            except Exception as e:
                self.logger.error(f"Error building graph for {file_path}: {e}")
                failed_files.append({
                    "path": file_path,
                    "error": str(e)
                })
        
        # Update graph stats
        self.graph_stats["files"] += len(file_nodes)
        self.graph_stats["classes"] += len(class_nodes)
        self.graph_stats["functions"] += len(function_nodes)
        self.graph_stats["relationships"] += relationship_count
        
        # Return results
        result = {
            "files_processed": len(asts),
            "files_deleted": deleted_count,
            "files_failed": len(failed_files),
            "nodes_created": len(file_nodes) + len(class_nodes) + len(function_nodes),
            "relationships_created": relationship_count,
            "graph_stats": self.graph_stats,
            "failed_files": failed_files[:10]  # Include only first 10 failed files
        }
        
        self.logger.info(f"Graph building completed: {len(file_nodes)} files processed")
        return HandlerResponse.success(result)
    
    def _process_ast(self, ast_data: Dict[str, Any], file_id: str, file_path: str,
                  language: str, repository: str, repository_url: str) -> Dict[str, Any]:
        """
        Process an AST into graph nodes and relationships.
        
        Args:
            ast_data: AST dictionary
            file_id: Unique file ID
            file_path: Path to the file
            language: Programming language
            repository: Repository name
            repository_url: Repository URL
            
        Returns:
            Dictionary with processing results
        """
        # Create file node
        self.neo4j_tool.create_file_node(
            file_id=file_id,
            path=file_path,
            language=language,
            repo_path=repository
        )
        
        class_nodes = []
        function_nodes = []
        relationship_count = 0
        
        # Extract root node
        root = ast_data.get("root", {})
        if not root:
            return {
                "class_nodes": class_nodes,
                "function_nodes": function_nodes,
                "relationship_count": relationship_count
            }
        
        # Process imports if enabled
        if self.use_imports and "imports" in ast_data:
            imports = ast_data.get("imports", [])
            for import_name in imports:
                self.neo4j_tool.create_import_relationship(file_id, import_name)
                relationship_count += 1
        
        # Process classes
        classes = find_entity_in_ast(root, "ClassDef")
        for class_ast in classes:
            class_info = get_class_info(class_ast)
            class_id = f"{file_id}_{class_info['name']}"
            
            # Create class node
            self.neo4j_tool.create_class_node(
                class_id=class_id,
                name=class_info['name'],
                file_id=file_id,
                start_line=class_info['start_line'],
                end_line=class_info['end_line'],
                docstring=class_info['docstring']
            )
            class_nodes.append(class_id)
            
            # Create CONTAINS relationship
            self.neo4j_tool.create_relationship(
                from_id=file_id,
                to_id=class_id,
                rel_type="CONTAINS"
            )
            relationship_count += 1
            
            # Process inheritance if enabled
            if self.use_inheritance and class_info['bases']:
                for base in class_info['bases']:
                    # Try to find base class node
                    base_query = f"""
                    MATCH (c:Class)
                    WHERE c.name = '{base}'
                    RETURN c.id as id
                    LIMIT 1
                    """
                    
                    try:
                        results = self.neo4j_tool.execute_cypher(base_query)
                        if results and "id" in results[0]:
                            base_id = results[0]["id"]
                            # Create EXTENDS relationship
                            self.neo4j_tool.create_relationship(
                                from_id=class_id,
                                to_id=base_id,
                                rel_type="EXTENDS"
                            )
                            relationship_count += 1
                    except Exception as e:
                        self.logger.warning(f"Error processing inheritance for {class_info['name']}: {e}")
            
            # Process methods
            for method_info in class_info['methods']:
                method_id = f"{class_id}_{method_info['name']}"
                
                # Create function node
                self.neo4j_tool.create_function_node(
                    function_id=method_id,
                    name=method_info['name'],
                    file_id=file_id,
                    class_id=class_id,
                    start_line=method_info['start_line'],
                    end_line=method_info['end_line'],
                    params=method_info['params'],
                    docstring=method_info['docstring'],
                    is_method=True
                )
                function_nodes.append(method_id)
                
                # Create CONTAINS relationship
                self.neo4j_tool.create_relationship(
                    from_id=class_id,
                    to_id=method_id,
                    rel_type="CONTAINS"
                )
                relationship_count += 1
        
        # Process functions (not methods)
        functions = find_entity_in_ast(root, "FunctionDef")
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
            function_id = f"{file_id}_{func_info['name']}"
            
            # Create function node
            self.neo4j_tool.create_function_node(
                function_id=function_id,
                name=func_info['name'],
                file_id=file_id,
                start_line=func_info['start_line'],
                end_line=func_info['end_line'],
                params=func_info['params'],
                docstring=func_info['docstring'],
                is_method=False
            )
            function_nodes.append(function_id)
            
            # Create CONTAINS relationship
            self.neo4j_tool.create_relationship(
                from_id=file_id,
                to_id=function_id,
                rel_type="CONTAINS"
            )
            relationship_count += 1
        
        # Process function calls if enabled
        if self.detect_calls:
            # Extract calls from AST
            calls = self._extract_calls(ast_data)
            if calls:
                for call in calls:
                    self._process_call(file_id, call)
                    relationship_count += 1
        
        return {
            "class_nodes": class_nodes,
            "function_nodes": function_nodes,
            "relationship_count": relationship_count
        }
    
    def _extract_calls(self, ast_data: Dict[str, Any]) -> List[str]:
        """
        Extract function/method calls from AST.
        
        Args:
            ast_data: AST dictionary
            
        Returns:
            List of function/method call names
        """
        # In a real implementation, this would parse the AST to find Call nodes
        # For now, use the calls field if provided
        if "calls" in ast_data:
            return ast_data["calls"]
        
        # Simple extraction from the AST
        calls = []
        root = ast_data.get("root", {})
        if root:
            call_nodes = find_entity_in_ast(root, "Call")
            for call_node in call_nodes:
                # Try to extract function name
                if "attributes" in call_node and "func" in call_node["attributes"]:
                    func = call_node["attributes"]["func"]
                    if isinstance(func, dict) and "attributes" in func and "id" in func["attributes"]:
                        calls.append(func["attributes"]["id"])
                
                # Try children for attribute-based calls
                if "children" in call_node:
                    for child in call_node["children"]:
                        if child.get("type") == "Name" and "text" in child:
                            calls.append(child["text"])
        
        return calls
    
    def _process_call(self, source_id: str, call_name: str) -> bool:
        """
        Process a function call and create CALLS relationship.
        
        Args:
            source_id: ID of the source node
            call_name: Name of the called function
            
        Returns:
            True if call was processed, False otherwise
        """
        try:
            # Find target function nodes
            target_nodes = self.neo4j_tool.find_function_by_name(call_name)
            
            if target_nodes:
                # Create CALLS relationship to each target
                for target_id in target_nodes:
                    self.neo4j_tool.create_relationship(
                        from_id=source_id,
                        to_id=target_id,
                        rel_type="CALLS"
                    )
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Error processing call to {call_name}: {e}")
            return False
    
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
                file_id = hashlib.md5(file_path.encode()).hexdigest()
                
                # Delete file node and all its relationships
                self.neo4j_tool.delete_file_and_contents(file_id)
                count += 1
                self.logger.info(f"Removed {file_path} from graph")
            except Exception as e:
                self.logger.error(f"Error removing {file_path} from graph: {e}")
        
        return count