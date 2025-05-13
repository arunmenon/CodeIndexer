"""
Code Parser Agent

Agent responsible for parsing source files into AST structures.
"""

import logging
import os
from typing import Dict, Any, List, Optional, Tuple

from google.adk import Agent
from google.adk.tools.google_api_tool import AgentContext, HandlerResponse
from google.adk.tools.google_api_tool import ToolResponse


class CodeParserAgent(Agent):
    """
    Agent responsible for parsing source files into AST structures.
    
    This agent takes source files, detects their language, parses them into AST
    structures using the appropriate parser, and passes the structured data to
    the graph builder agent.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the code parser agent.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self.logger = logging.getLogger("code_parser_agent")
        
        # Configure defaults
        self.max_file_size = config.get("max_file_size", 1024 * 1024)  # 1MB
        self.batch_size = config.get("batch_size", 10)
        
        # State
        self.ast_extractor = None
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        self.context = context
        
        # Get AST extractor tool
        tool_response = context.get_tool("ast_extractor_tool")
        if tool_response.status.is_success():
            self.ast_extractor = tool_response.tool
            self.logger.info("Successfully acquired AST extractor tool")
        else:
            self.logger.error("Failed to acquire AST extractor tool: %s", 
                             tool_response.status.message)
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Parse source files into AST structures.
        
        Args:
            input_data: Dictionary containing files to parse
            
        Returns:
            HandlerResponse with parsing results
        """
        self.logger.info("Starting code parser agent")
        
        # Check if AST extractor is available
        if not self.ast_extractor:
            return HandlerResponse.error("AST extractor tool not available")
        
        # Extract files from input
        files = input_data.get("files", [])
        if not files:
            return HandlerResponse.error("No files to parse")
        
        repository = input_data.get("repository", "")
        repository_url = input_data.get("url", "")
        commit = input_data.get("commit", "")
        branch = input_data.get("branch", "")
        is_full_indexing = input_data.get("is_full_indexing", False)
        
        # Create batches
        file_batches = self._create_batches(files)
        
        # Process each batch
        parsed_files = []
        failed_files = []
        
        for batch_index, file_batch in enumerate(file_batches):
            self.logger.info(f"Processing batch {batch_index + 1}/{len(file_batches)}")
            
            # Parse files in batch
            for file_data in file_batch:
                file_path = file_data.get("path", "")
                content = file_data.get("content", "")
                
                if not file_path or not content:
                    self.logger.warning(f"Skipping file with missing path or content")
                    continue
                
                # Check file size
                if len(content) > self.max_file_size:
                    self.logger.warning(f"Skipping large file: {file_path}")
                    failed_files.append({
                        "path": file_path,
                        "error": "File too large"
                    })
                    continue
                
                # Parse file
                parse_result = self._parse_file(
                    file_path=file_path,
                    content=content,
                    repository=repository,
                    repository_url=repository_url,
                    commit=commit,
                    branch=branch
                )
                
                if parse_result.get("status") == "success":
                    parsed_files.append(parse_result.get("ast"))
                else:
                    failed_files.append({
                        "path": file_path,
                        "error": parse_result.get("error", "Unknown error")
                    })
        
        # Send parsed files to graph builder
        send_result = self._send_to_graph_builder(
            parsed_files=parsed_files,
            repository=repository,
            repository_url=repository_url,
            commit=commit,
            branch=branch,
            is_full_indexing=is_full_indexing
        )
        
        return HandlerResponse.success({
            "files_parsed": len(parsed_files),
            "files_failed": len(failed_files),
            "graph_builder_status": send_result.get("status", "unknown"),
            "failed_files": failed_files[:10]  # Include only the first 10 failed files
        })
    
    def _create_batches(self, files: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Create batches of files for processing.
        
        Args:
            files: List of file data
            
        Returns:
            List of file data batches
        """
        batches = []
        for i in range(0, len(files), self.batch_size):
            batches.append(files[i:i + self.batch_size])
        return batches
    
    def _parse_file(self, file_path: str, content: str, repository: str,
                  repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Parse a single file.
        
        Args:
            file_path: Path to the file
            content: File content
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            Dictionary with parsing results
        """
        try:
            # Extract file extension for language detection
            _, ext = os.path.splitext(file_path)
            
            # Extract AST
            ast_dict = self.ast_extractor.extract_ast(content, file_path=file_path)
            
            # Add metadata
            ast_dict["repository"] = repository
            ast_dict["repository_url"] = repository_url
            ast_dict["commit"] = commit
            ast_dict["branch"] = branch
            ast_dict["file_path"] = file_path
            
            return {
                "status": "success",
                "ast": ast_dict
            }
            
        except Exception as e:
            self.logger.error(f"Failed to parse file {file_path}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _send_to_graph_builder(self, parsed_files: List[Dict[str, Any]],
                             repository: str, repository_url: str,
                             commit: str, branch: str, 
                             is_full_indexing: bool) -> Dict[str, Any]:
        """
        Send parsed files to graph builder.
        
        Args:
            parsed_files: List of parsed AST dictionaries
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            is_full_indexing: Whether this is a full indexing
            
        Returns:
            Dictionary with send results
        """
        if not parsed_files:
            return {
                "status": "success",
                "message": "No files to send"
            }
        
        try:
            # Prepare input for graph builder
            graph_builder_input = {
                "asts": parsed_files,
                "repository": repository,
                "repository_url": repository_url,
                "commit": commit,
                "branch": branch,
                "is_full_indexing": is_full_indexing
            }
            
            # Get graph builder agent
            tool_response = self.context.get_tool("graph_builder_agent")
            if not tool_response.status.is_success():
                return {
                    "status": "error",
                    "message": f"Failed to get graph builder agent: {tool_response.status.message}"
                }
            
            # Call graph builder agent
            graph_builder = tool_response.tool
            response = graph_builder.run(graph_builder_input)
            
            if not isinstance(response, ToolResponse) or not response.status.is_success():
                return {
                    "status": "error",
                    "message": f"Failed to send to graph builder: {response.status.message if isinstance(response, ToolResponse) else 'Unknown error'}"
                }
            
            return {
                "status": "success",
                "message": "Files sent to graph builder"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send to graph builder: {e}")
            return {
                "status": "error",
                "message": f"Failed to send to graph builder: {str(e)}"
            }