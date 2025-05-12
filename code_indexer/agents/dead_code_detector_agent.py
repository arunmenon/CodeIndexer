"""
Dead Code Detector Agent

This agent detects potentially unused code by analyzing call graphs in the knowledge base.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from google.adk import Agent, AgentContext
from google.adk.tooling import BaseTool

from code_indexer.tools.neo4j_tool import Neo4jTool


class DeadCodeDetectorAgent(Agent):
    """
    Agent responsible for detecting potentially unused code.
    
    This agent analyzes the code graph to find functions and methods that
    aren't called by any other code, helping identify dead code.
    """
    
    def __init__(self):
        """Initialize the Dead Code Detector Agent."""
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
    
    def run(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Detect potentially unused code in the graph.
        
        Args:
            inputs: Optional configuration for detection (can be empty)
            
        Returns:
            Dictionary with lists of potentially dead code
        """
        # Find potentially unused functions (non-public functions with no incoming CALLS)
        dead_functions = self._find_unused_functions()
        
        # Find potentially unused classes (no incoming CALLS to any methods)
        dead_classes = self._find_unused_classes()
        
        # Log findings
        self.logger.info(f"Found {len(dead_functions)} potentially unused functions")
        self.logger.info(f"Found {len(dead_classes)} potentially unused classes")
        
        # Return results
        return {
            "dead_functions": dead_functions,
            "dead_classes": dead_classes,
            "timestamp": self.context.state.get("timestamp", "")
        }
    
    def _find_unused_functions(self) -> List[Dict[str, Any]]:
        """
        Find functions that aren't called by any other code.
        
        Returns:
            List of potentially unused functions with metadata
        """
        # Cypher query to find functions with no incoming CALLS relationships
        # Excludes main/public functions which might be entry points
        query = """
        MATCH (f:Function)
        WHERE NOT ()-[:CALLS]->(f)
        AND NOT f.name IN ['main', '__main__', '__init__']
        AND NOT f.name STARTS WITH 'test_'
        AND NOT f.name STARTS WITH 'public '
        RETURN f.id, f.name, f.file_id, f.start_line, f.end_line,
               f.is_method, f.class_id, f.docstring
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query)
            
            # Enhance results with file path
            for result in results:
                file_id = result.get("f.file_id")
                if file_id:
                    file_info = self._get_file_info(file_id)
                    result["file_path"] = file_info.get("path", "")
                    result["language"] = file_info.get("language", "")
            
            return results
        except Exception as e:
            self.logger.error(f"Error finding unused functions: {e}")
            return []
    
    def _find_unused_classes(self) -> List[Dict[str, Any]]:
        """
        Find classes whose methods aren't called by any other code.
        
        Returns:
            List of potentially unused classes with metadata
        """
        # Cypher query to find classes where no methods have incoming CALLS
        query = """
        MATCH (c:Class)
        WHERE NOT EXISTS {
            MATCH (c)-[:CONTAINS]->(m:Function)
            WHERE ()-[:CALLS]->(m)
        }
        AND NOT c.name STARTS WITH 'Test'
        RETURN c.id, c.name, c.file_id, c.start_line, c.end_line, c.docstring
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query)
            
            # Enhance results with file path
            for result in results:
                file_id = result.get("c.file_id")
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
        RETURN f.path, f.language
        """
        
        try:
            results = self.neo4j_tool.execute_cypher(query, {"file_id": file_id})
            if results:
                return results[0]
            return {}
        except Exception:
            return {}