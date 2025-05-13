"""
Dead Code Detector Agent

This agent detects potentially unused code by analyzing call graphs in the knowledge base.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Union

from google.adk import Agent
from google.adk.tools.google_api_tool import AgentContext, HandlerResponse
from google.adk.tools.google_api_tool import ToolResponse, ToolStatus

from code_indexer.tools.neo4j_tool import Neo4jTool


class DeadCodeDetectorAgent(Agent):
    """
    Agent responsible for detecting potentially unused code.
    
    This agent analyzes the code graph to find functions and methods that
    aren't called by any other code, helping identify dead code.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Dead Code Detector Agent.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self.logger = logging.getLogger("dead_code_detector_agent")
        
        # Configure defaults
        self.ignore_entry_points = config.get("ignore_entry_points", True)
        self.ignore_tests = config.get("ignore_tests", True)
        self.max_results = config.get("max_results", 100)
        
        # State
        self.neo4j_tool = None
    
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
        Detect potentially unused code in the graph.
        
        Args:
            input_data: Dictionary with detection configuration
            
        Returns:
            HandlerResponse with detection results
        """
        self.logger.info("Starting dead code detection")
        
        # Check if Neo4j tool is available
        if not self.neo4j_tool:
            return HandlerResponse.error("Neo4j tool not available")
        
        # Extract configuration
        repository = input_data.get("repository", "")
        scope = input_data.get("scope", "all")  # all, functions, classes
        exclude_patterns = input_data.get("exclude_patterns", [])
        max_results = input_data.get("max_results", self.max_results)
        
        # Find potentially unused code based on scope
        dead_functions = []
        dead_classes = []
        
        if scope in ["all", "functions"]:
            dead_functions = self._find_unused_functions(
                repository=repository,
                exclude_patterns=exclude_patterns,
                max_results=max_results
            )
        
        if scope in ["all", "classes"]:
            dead_classes = self._find_unused_classes(
                repository=repository,
                exclude_patterns=exclude_patterns,
                max_results=max_results
            )
        
        # Log findings
        self.logger.info(f"Found {len(dead_functions)} potentially unused functions")
        self.logger.info(f"Found {len(dead_classes)} potentially unused classes")
        
        # Structure results in a standardized format
        results = self._format_results(dead_functions, dead_classes)
        
        # Return results
        response_data = {
            "repository": repository,
            "scope": scope,
            "total_results": len(results),
            "results": results,
            "timestamp": time.time()
        }
        
        self.logger.info("Dead code detection completed successfully")
        return HandlerResponse.success(response_data)
    
    def _find_unused_functions(self, repository: str, exclude_patterns: List[str], 
                             max_results: int) -> List[Dict[str, Any]]:
        """
        Find functions that aren't called by any other code.
        
        Args:
            repository: Repository name/path filter
            exclude_patterns: Patterns to exclude from results
            max_results: Maximum number of results to return
            
        Returns:
            List of potentially unused functions with metadata
        """
        # Build repository filter clause
        repo_filter = ""
        if repository:
            repo_filter = f"AND f.repo_path = '{repository}' "
        
        # Build exclusion patterns
        exclusion_clause = "AND NOT f.name IN ['main', '__main__', '__init__']"
        if self.ignore_tests:
            exclusion_clause += " AND NOT f.name STARTS WITH 'test_'"
            exclusion_clause += " AND NOT f.name STARTS WITH 'Test'"
        
        # Add custom exclusions
        for pattern in exclude_patterns:
            exclusion_clause += f" AND NOT f.name =~ '{pattern}'"
        
        # Cypher query to find functions with no incoming CALLS relationships
        query = f"""
        MATCH (f:Function)
        WHERE NOT ()-[:CALLS]->(f)
        {repo_filter}
        {exclusion_clause}
        RETURN f.id as id, f.name as name, f.file_id as file_id, 
               f.start_line as start_line, f.end_line as end_line,
               f.is_method as is_method, f.class_id as class_id, 
               f.docstring as docstring
        LIMIT {max_results}
        """
        
        try:
            # Execute query
            tool_response = self.neo4j_tool.execute_query({
                "query": query
            })
            
            if not isinstance(tool_response, ToolResponse) or not tool_response.status.is_success():
                self.logger.error(f"Query failed: {tool_response.status.message if isinstance(tool_response, ToolResponse) else 'Unknown error'}")
                return []
            
            results = tool_response.data.get("results", [])
            
            # Enhance results with file path
            for result in results:
                file_id = result.get("file_id")
                if file_id:
                    file_info = self._get_file_info(file_id)
                    result["file_path"] = file_info.get("path", "")
                    result["language"] = file_info.get("language", "")
            
            return results
        except Exception as e:
            self.logger.error(f"Error finding unused functions: {e}")
            return []
    
    def _find_unused_classes(self, repository: str, exclude_patterns: List[str], 
                           max_results: int) -> List[Dict[str, Any]]:
        """
        Find classes whose methods aren't called by any other code.
        
        Args:
            repository: Repository name/path filter
            exclude_patterns: Patterns to exclude from results
            max_results: Maximum number of results to return
            
        Returns:
            List of potentially unused classes with metadata
        """
        # Build repository filter clause
        repo_filter = ""
        if repository:
            repo_filter = f"AND EXISTS {{ MATCH (f:File) WHERE f.id = c.file_id AND f.repo_path = '{repository}' }} "
        
        # Build exclusion patterns
        exclusion_clause = ""
        if self.ignore_tests:
            exclusion_clause += "AND NOT c.name STARTS WITH 'Test' "
            exclusion_clause += "AND NOT c.name ENDS WITH 'Test' "
            exclusion_clause += "AND NOT c.name ENDS WITH 'TestCase' "
        
        # Add custom exclusions
        for pattern in exclude_patterns:
            exclusion_clause += f"AND NOT c.name =~ '{pattern}' "
        
        # Cypher query to find classes where no methods have incoming CALLS
        query = f"""
        MATCH (c:Class)
        WHERE NOT EXISTS {{
            MATCH (c)-[:CONTAINS]->(m:Function)
            WHERE ()-[:CALLS]->(m)
        }}
        {repo_filter}
        {exclusion_clause}
        RETURN c.id as id, c.name as name, c.file_id as file_id, 
               c.start_line as start_line, c.end_line as end_line, 
               c.docstring as docstring
        LIMIT {max_results}
        """
        
        try:
            # Execute query
            tool_response = self.neo4j_tool.execute_query({
                "query": query
            })
            
            if not isinstance(tool_response, ToolResponse) or not tool_response.status.is_success():
                self.logger.error(f"Query failed: {tool_response.status.message if isinstance(tool_response, ToolResponse) else 'Unknown error'}")
                return []
            
            results = tool_response.data.get("results", [])
            
            # Enhance results with file path
            for result in results:
                file_id = result.get("file_id")
                if file_id:
                    file_info = self._get_file_info(file_id)
                    result["file_path"] = file_info.get("path", "")
                    result["language"] = file_info.get("language", "")
            
            return results
        except Exception as e:
            self.logger.error(f"Error finding unused classes: {e}")
            return []
    
    def _get_file_info(self, file_id: str) -> Dict[str, Any]:
        """
        Get file information from the graph.
        
        Args:
            file_id: ID of the file
            
        Returns:
            Dictionary with file information
        """
        query = """
        MATCH (f:File {id: $file_id})
        RETURN f.path as path, f.language as language
        """
        
        try:
            tool_response = self.neo4j_tool.execute_query({
                "query": query,
                "params": {"file_id": file_id}
            })
            
            if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                results = tool_response.data.get("results", [])
                if results:
                    return results[0]
            
            return {}
        except Exception as e:
            self.logger.error(f"Error getting file info: {e}")
            return {}
    
    def _format_results(self, functions: List[Dict[str, Any]], 
                      classes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format results into a standardized structure.
        
        Args:
            functions: List of unused functions
            classes: List of unused classes
            
        Returns:
            Formatted list of dead code findings
        """
        formatted_results = []
        
        # Format functions
        for func in functions:
            formatted_results.append({
                "type": "function",
                "name": func.get("name", ""),
                "is_method": func.get("is_method", False),
                "file_path": func.get("file_path", ""),
                "language": func.get("language", ""),
                "start_line": func.get("start_line", 0),
                "end_line": func.get("end_line", 0),
                "class_name": self._get_class_name(func.get("class_id", "")),
                "docstring": func.get("docstring", "")
            })
        
        # Format classes
        for cls in classes:
            formatted_results.append({
                "type": "class",
                "name": cls.get("name", ""),
                "file_path": cls.get("file_path", ""),
                "language": cls.get("language", ""),
                "start_line": cls.get("start_line", 0),
                "end_line": cls.get("end_line", 0),
                "docstring": cls.get("docstring", "")
            })
        
        return formatted_results
    
    def _get_class_name(self, class_id: str) -> str:
        """
        Get class name from class ID.
        
        Args:
            class_id: ID of the class
            
        Returns:
            Class name or empty string
        """
        if not class_id:
            return ""
        
        query = """
        MATCH (c:Class {id: $class_id})
        RETURN c.name as name
        """
        
        try:
            tool_response = self.neo4j_tool.execute_query({
                "query": query,
                "params": {"class_id": class_id}
            })
            
            if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                results = tool_response.data.get("results", [])
                if results and "name" in results[0]:
                    return results[0]["name"]
            
            return ""
        except Exception:
            return ""