"""
Search API

Provides a simple API for accessing the Code Indexer's search functionality.
"""

import logging
from typing import Dict, Any, List, Optional

from google.adk.tools.google_api_tool import AgentContext

class CodeSearchAPI:
    """
    API for searching code using the Code Indexer.
    
    This class provides a simple interface for accessing the search functionality
    without having to interact with the individual agents directly.
    """
    
    def __init__(self, context: AgentContext):
        """
        Initialize the search API.
        
        Args:
            context: Agent context providing access to tools and agents
        """
        self.context = context
        self.logger = logging.getLogger("code_search_api")
        
        # Get search orchestrator
        tool_response = context.get_tool("search_orchestrator_agent")
        if tool_response.status.is_success():
            self.search_orchestrator = tool_response.tool
            self.logger.info("Successfully acquired search orchestrator")
        else:
            self.search_orchestrator = None
            self.logger.error("Failed to acquire search orchestrator: %s", 
                             tool_response.status.message)
    
    def search(self, query: str, search_type: str = "hybrid", 
              max_results: int = 10, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Search for code using natural language query.
        
        Args:
            query: Natural language query
            search_type: Type of search (hybrid, vector, graph)
            max_results: Maximum number of results to return
            filters: Optional filters to apply
            
        Returns:
            Dictionary with search results and answer
        """
        if not self.search_orchestrator:
            return {
                "error": "Search orchestrator not available",
                "success": False
            }
        
        try:
            # Prepare search parameters
            search_params = {
                "query": query,
                "search_type": search_type,
                "max_results": max_results,
                "filters": filters or {}
            }
            
            # Call the search orchestrator
            response = self.search_orchestrator.run(search_params)
            
            if response.status.is_success():
                result_data = response.data
                
                # Format the response for API consumers
                formatted_response = {
                    "success": True,
                    "query": query,
                    "answer": result_data.get("answer", ""),
                    "code_snippets": result_data.get("code_snippets", []),
                    "total_results": result_data.get("total_results", 0),
                    "search_type": search_type
                }
                
                # Include detailed results if available
                if "vector_results" in result_data or "graph_results" in result_data:
                    formatted_response["detailed_results"] = {
                        "vector": result_data.get("vector_results", []),
                        "graph": result_data.get("graph_results", [])
                    }
                
                return formatted_response
            else:
                return {
                    "error": response.status.message,
                    "success": False,
                    "query": query
                }
        except Exception as e:
            self.logger.error(f"Error performing search: {e}")
            return {
                "error": str(e),
                "success": False,
                "query": query
            }
    
    def search_by_file(self, file_path: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Search for code related to a specific file.
        
        Args:
            file_path: Path to the file
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        return self.search(
            query=f"Find all code related to the file {file_path}",
            filters={"file_path": file_path},
            max_results=max_results
        )
    
    def search_by_function(self, function_name: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Search for a specific function and its usages.
        
        Args:
            function_name: Name of the function
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        return self.search(
            query=f"Find the definition and usages of the function {function_name}",
            max_results=max_results
        )
    
    def search_by_class(self, class_name: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Search for a specific class and its relationships.
        
        Args:
            class_name: Name of the class
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        return self.search(
            query=f"Find the definition, methods, and inheritance of the class {class_name}",
            max_results=max_results
        )
    
    def explain_code(self, code_entity: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Get an explanation of a code entity.
        
        Args:
            code_entity: Name of the code entity (function, class, etc.)
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with explanation and related code
        """
        return self.search(
            query=f"Explain what {code_entity} does and how it works",
            max_results=max_results
        )