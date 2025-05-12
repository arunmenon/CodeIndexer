"""
Search Orchestrator Agent

Agent responsible for orchestrating the search flow across multiple search agents.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union

from google.adk.api.agent import Agent, AgentContext, HandlerResponse
from google.adk.api.tool import ToolResponse

class SearchOrchestratorAgent(Agent):
    """
    Agent responsible for orchestrating the search flow.
    
    This agent coordinates the interaction between the query agent,
    vector search agent, graph search agent, and answer composer agent
    to provide a complete end-to-end search experience.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the search orchestrator agent.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self.logger = logging.getLogger("search_orchestrator_agent")
        
        # Configure defaults
        self.search_types = config.get("search_types", ["hybrid"])  # hybrid, vector, graph
        self.enable_parallel = config.get("enable_parallel", True)
        self.vector_store_collection = config.get("vector_store_collection", "code_embeddings")
        
        # Available agents
        self.query_agent = None
        self.vector_search_agent = None
        self.graph_search_agent = None
        self.answer_composer_agent = None
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        self.context = context
        
        # Get query agent
        tool_response = context.get_tool("query_agent")
        if tool_response.status.is_success():
            self.query_agent = tool_response.tool
            self.logger.info("Successfully acquired query agent")
        else:
            self.logger.error("Failed to acquire query agent: %s", 
                             tool_response.status.message)
        
        # Get vector search agent
        tool_response = context.get_tool("vector_search_agent")
        if tool_response.status.is_success():
            self.vector_search_agent = tool_response.tool
            self.logger.info("Successfully acquired vector search agent")
        else:
            self.logger.error("Failed to acquire vector search agent: %s", 
                             tool_response.status.message)
        
        # Get graph search agent
        tool_response = context.get_tool("graph_search_agent")
        if tool_response.status.is_success():
            self.graph_search_agent = tool_response.tool
            self.logger.info("Successfully acquired graph search agent")
        else:
            self.logger.error("Failed to acquire graph search agent: %s", 
                             tool_response.status.message)
        
        # Get answer composer agent
        tool_response = context.get_tool("answer_composer_agent")
        if tool_response.status.is_success():
            self.answer_composer_agent = tool_response.tool
            self.logger.info("Successfully acquired answer composer agent")
        else:
            self.logger.error("Failed to acquire answer composer agent: %s", 
                             tool_response.status.message)
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Orchestrate the search flow.
        
        Args:
            input_data: Dictionary containing the query and search parameters
            
        Returns:
            HandlerResponse with search results and answer
        """
        self.logger.info("Orchestrating search flow")
        
        # Extract query from input
        query = input_data.get("query", "")
        if not query:
            return HandlerResponse.error("No query provided")
        
        # Extract search parameters
        search_type = input_data.get("search_type", "hybrid")
        max_results = input_data.get("max_results", 10)
        filters = input_data.get("filters", {})
        
        # Validate agents
        if not self.query_agent:
            return HandlerResponse.error("Query agent not available")
        
        # Process query to get search specification
        query_response = self.query_agent.run({
            "query": query,
            "search_type": search_type,
            "max_results": max_results,
            "filters": filters
        })
        
        if not isinstance(query_response, ToolResponse) or not query_response.status.is_success():
            return HandlerResponse.error(f"Query processing failed: {query_response.status.message if isinstance(query_response, ToolResponse) else 'Unknown error'}")
        
        # Get search specification
        search_spec = query_response.data.get("search_spec", {})
        
        # Determine which search types to use
        search_types_to_use = []
        if search_type == "hybrid":
            search_types_to_use = ["vector", "graph"]
        else:
            search_types_to_use = [search_type]
        
        # Perform searches based on search types
        vector_results = []
        graph_results = []
        
        # If parallel search is enabled, run searches concurrently
        if self.enable_parallel and ("vector" in search_types_to_use and "graph" in search_types_to_use):
            vector_results, graph_results = self._perform_parallel_search(search_spec, max_results)
        else:
            # Run searches sequentially
            if "vector" in search_types_to_use and self.vector_search_agent:
                vector_results = self._perform_vector_search(search_spec, max_results)
            
            if "graph" in search_types_to_use and self.graph_search_agent:
                graph_results = self._perform_graph_search(search_spec, max_results)
        
        # Compose answer if answer composer agent is available
        if self.answer_composer_agent:
            answer_response = self.answer_composer_agent.run({
                "original_query": query,
                "search_spec": search_spec,
                "vector_results": vector_results,
                "graph_results": graph_results
            })
            
            if isinstance(answer_response, ToolResponse) and answer_response.status.is_success():
                answer_data = answer_response.data
            else:
                answer_data = {
                    "answer": "I found some information but couldn't compose a complete answer.",
                    "code_snippets": [],
                    "query": query
                }
        else:
            # Create a simple answer if answer composer is not available
            answer_data = {
                "answer": f"I found {len(vector_results) + len(graph_results)} results related to your query.",
                "code_snippets": [],
                "query": query
            }
        
        # Combine all results for the response
        response_data = {
            "answer": answer_data.get("answer", ""),
            "code_snippets": answer_data.get("code_snippets", []),
            "query": query,
            "search_spec": search_spec,
            "vector_results": vector_results,
            "graph_results": graph_results,
            "total_results": len(vector_results) + len(graph_results)
        }
        
        self.logger.info("Search orchestration completed successfully")
        return HandlerResponse.success(response_data)
    
    def _perform_vector_search(self, search_spec: Dict[str, Any], 
                             max_results: int) -> List[Dict[str, Any]]:
        """
        Perform vector search.
        
        Args:
            search_spec: Search specification
            max_results: Maximum number of results to return
            
        Returns:
            Vector search results
        """
        if not self.vector_search_agent:
            self.logger.error("Vector search agent not available")
            return []
        
        try:
            # Prepare search parameters
            search_params = {
                "search_spec": search_spec,
                "collection": self.vector_store_collection,
                "max_results": max_results
            }
            
            # Call the vector search agent
            tool_response = self.vector_search_agent.run(search_params)
            
            if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                results = tool_response.data.get("results", [])
                self.logger.info(f"Vector search found {len(results)} results")
                return results
            else:
                self.logger.error(f"Vector search failed: {tool_response.status.message if isinstance(tool_response, ToolResponse) else 'Unknown error'}")
                return []
        except Exception as e:
            self.logger.error(f"Error performing vector search: {e}")
            return []
    
    def _perform_graph_search(self, search_spec: Dict[str, Any], 
                            max_results: int) -> List[Dict[str, Any]]:
        """
        Perform graph search.
        
        Args:
            search_spec: Search specification
            max_results: Maximum number of results to return
            
        Returns:
            Graph search results
        """
        if not self.graph_search_agent:
            self.logger.error("Graph search agent not available")
            return []
        
        try:
            # Prepare search parameters
            search_params = {
                "search_spec": search_spec,
                "max_results": max_results
            }
            
            # Call the graph search agent
            tool_response = self.graph_search_agent.run(search_params)
            
            if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                results = tool_response.data.get("results", [])
                self.logger.info(f"Graph search found {len(results)} results")
                return results
            else:
                self.logger.error(f"Graph search failed: {tool_response.status.message if isinstance(tool_response, ToolResponse) else 'Unknown error'}")
                return []
        except Exception as e:
            self.logger.error(f"Error performing graph search: {e}")
            return []
    
    def _perform_parallel_search(self, search_spec: Dict[str, Any], 
                               max_results: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Perform vector and graph searches in parallel.
        
        Args:
            search_spec: Search specification
            max_results: Maximum number of results to return
            
        Returns:
            Tuple of (vector_results, graph_results)
        """
        # For this simplified implementation, just call the methods sequentially
        # In a real implementation, this would use async/await or threading
        
        vector_results = self._perform_vector_search(search_spec, max_results)
        graph_results = self._perform_graph_search(search_spec, max_results)
        
        return vector_results, graph_results