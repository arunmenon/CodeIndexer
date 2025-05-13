"""
Git Ingestion Agent

Agent responsible for monitoring repositories and detecting code changes.
"""

import logging
import json
import os
import time
from typing import Dict, Any, List, Optional, Set

from code_indexer.agents.adk_adapter import Agent, AgentContext, HandlerResponse, ToolResponse, init_agent

@init_agent(name="git_ingestion_agent")
class GitIngestionAgent(Agent):
    """
    Agent responsible for monitoring repositories and detecting code changes.
    
    This agent monitors Git repositories, detects code changes since the last
    indexing, and triggers the indexing pipeline for changed files.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the git ingestion agent.
        
        Args:
            config: Configuration dictionary
        """
        # The Agent initialization is handled by the decorator
        # This method is not directly called - wrapper setup is done in init_wrapper
        pass
    
    def init_wrapper(self, wrapper, config: Dict[str, Any], *args, **kwargs):
        """
        Initialize the wrapper with agent state.
        
        Args:
            wrapper: Agent wrapper instance
            config: Configuration dictionary
        """
        # Configure defaults from config dictionary
        wrapper.repositories = config.get('repositories', [])
        wrapper.default_branch = config.get('default_branch', 'main')
        wrapper.polling_interval = config.get('polling_interval', 3600)  # 1 hour
        wrapper.commit_history_file = config.get('commit_history_file', 'commit_history.json')
        wrapper.max_file_batch = config.get('max_file_batch', 100)
        
        # State
        wrapper.commit_history = {}  # repository_url -> last_indexed_commit
        wrapper.git_tool = None
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        # Get wrapper for this agent
        wrapper = self.get_wrapper()
        wrapper.context = context
        
        # Get Git tool
        tool_response = context.get_tool("git_tool")
        if tool_response.status.is_success():
            wrapper.git_tool = tool_response.tool
            wrapper.logger.info("Successfully acquired Git tool")
        else:
            wrapper.logger.error("Failed to acquire Git tool: %s", 
                                tool_response.status.message)
        
        # Load commit history
        self._load_commit_history(wrapper)
    
    def run(self, wrapper, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Run the git ingestion agent.
        
        Args:
            wrapper: Agent wrapper with state
            input_data: Dictionary containing input parameters
            
        Returns:
            HandlerResponse with detection results
        """
        wrapper.logger.info("Starting Git ingestion agent")
        
        # Check if Git tool is available
        if not wrapper.git_tool:
            return HandlerResponse.error("Git tool not available")
        
        # Extract parameters from input
        repositories = input_data.get("repositories", wrapper.repositories)
        if not repositories:
            return HandlerResponse.error("No repositories specified")
        
        mode = input_data.get("mode", "incremental")  # incremental or full
        force_reindex = input_data.get("force_reindex", False)
        
        # Process each repository
        processing_results = []
        
        for repo_config in repositories:
            # Extract repository information
            repo_url = repo_config.get("url", "")
            branch = repo_config.get("branch", wrapper.default_branch)
            repo_name = repo_config.get("name", repo_url.split("/")[-1].replace(".git", ""))
            
            if not repo_url:
                wrapper.logger.warning("Repository URL not specified, skipping")
                continue
            
            # Process repository
            repo_result = self._process_repository(
                wrapper=wrapper,
                repo_url=repo_url, 
                branch=branch,
                repo_name=repo_name,
                mode=mode,
                force_reindex=force_reindex
            )
            
            processing_results.append(repo_result)
        
        # Save commit history
        self._save_commit_history(wrapper)
        
        return HandlerResponse.success({
            "results": processing_results,
            "repositories_processed": len(processing_results)
        })
    
    def _process_repository(self, wrapper, repo_url: str, branch: str, repo_name: str,
                          mode: str, force_reindex: bool) -> Dict[str, Any]:
        """
        Process a single repository.
        
        Args:
            wrapper: Agent wrapper with state
            repo_url: Repository URL
            branch: Branch to process
            repo_name: Repository name
            mode: Processing mode (incremental or full)
            force_reindex: Whether to force reindexing
            
        Returns:
            Dictionary with processing results
        """
        wrapper.logger.info(f"Processing repository {repo_name} ({repo_url})")
        
        # Clone or update repository
        success, repo_path = wrapper.git_tool.clone_repository(repo_url, branch)
        if not success:
            return {
                "repository": repo_name,
                "url": repo_url,
                "status": "error",
                "message": "Failed to clone repository"
            }
        
        # Get latest commit
        latest_commit_info = wrapper.git_tool.get_commit_info(repo_path)
        if not latest_commit_info:
            return {
                "repository": repo_name,
                "url": repo_url,
                "status": "error",
                "message": "Failed to get latest commit information"
            }
        
        latest_commit = latest_commit_info["hash"]
        
        # Get last indexed commit
        last_indexed_commit = wrapper.commit_history.get(repo_url)
        
        # Check if reindexing is needed
        if mode == "full" or force_reindex or not last_indexed_commit:
            # Full indexing
            changed_files = self._get_all_files(wrapper, repo_path)
            is_full_indexing = True
        else:
            # Incremental indexing
            changed_files_map = wrapper.git_tool.get_changed_files(
                repo_path, base_commit=last_indexed_commit, head_commit=latest_commit
            )
            
            # Filter out deleted files
            changed_files = [
                file_path for file_path, change_type in changed_files_map.items()
                if change_type != "D"  # Skip deleted files
            ]
            
            is_full_indexing = False
        
        # Filter indexable files
        indexable_files = wrapper.git_tool.filter_indexable_files(repo_path, changed_files)
        
        # Update commit history
        wrapper.commit_history[repo_url] = latest_commit
        
        # If no files to index, return success
        if not indexable_files:
            return {
                "repository": repo_name,
                "url": repo_url,
                "status": "success",
                "indexing_type": "full" if is_full_indexing else "incremental",
                "commit": latest_commit,
                "files_detected": 0,
                "files_processed": 0,
                "message": "No files to index"
            }
        
        # Process files in batches
        file_batches = self._create_file_batches(wrapper, indexable_files)
        files_processed = 0
        
        for batch_index, file_batch in enumerate(file_batches):
            wrapper.logger.info(f"Processing batch {batch_index + 1}/{len(file_batches)}")
            
            # Process batch of files
            batch_result = self._process_file_batch(
                wrapper=wrapper,
                repo_path=repo_path,
                repo_url=repo_url,
                repo_name=repo_name,
                file_batch=file_batch,
                commit=latest_commit,
                branch=branch,
                is_full_indexing=is_full_indexing
            )
            
            if batch_result.get("status") == "success":
                files_processed += batch_result.get("files_processed", 0)
            else:
                wrapper.logger.error(f"Failed to process batch: {batch_result.get('message')}")
        
        return {
            "repository": repo_name,
            "url": repo_url,
            "status": "success",
            "indexing_type": "full" if is_full_indexing else "incremental",
            "commit": latest_commit,
            "files_detected": len(indexable_files),
            "files_processed": files_processed,
            "message": f"Processed {files_processed} files"
        }
    
    def _get_all_files(self, wrapper, repo_path: str) -> List[str]:
        """
        Get all files in a repository.
        
        Args:
            wrapper: Agent wrapper with state
            repo_path: Path to the repository
            
        Returns:
            List of file paths
        """
        all_files = []
        
        # Walk through the repository
        for root, dirs, files in os.walk(repo_path):
            # Skip .git directory
            if ".git" in dirs:
                dirs.remove(".git")
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                all_files.append(rel_path)
        
        return all_files
    
    def _create_file_batches(self, wrapper, files: List[str]) -> List[List[str]]:
        """
        Create batches of files for processing.
        
        Args:
            wrapper: Agent wrapper with state
            files: List of file paths
            
        Returns:
            List of file path batches
        """
        batches = []
        for i in range(0, len(files), wrapper.max_file_batch):
            batches.append(files[i:i + wrapper.max_file_batch])
        return batches
    
    def _process_file_batch(self, wrapper, repo_path: str, repo_url: str, repo_name: str,
                          file_batch: List[str], commit: str, branch: str,
                          is_full_indexing: bool) -> Dict[str, Any]:
        """
        Process a batch of files.
        
        Args:
            wrapper: Agent wrapper with state
            repo_path: Path to the repository
            repo_url: Repository URL
            repo_name: Repository name
            file_batch: List of file paths to process
            commit: Commit hash
            branch: Branch name
            is_full_indexing: Whether this is a full indexing
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Prepare file data
            file_data = []
            
            for file_path in file_batch:
                # Get file content
                content = wrapper.git_tool.get_file_content(repo_path, file_path, commit)
                if content is None:
                    wrapper.logger.warning(f"Failed to get content for file {file_path}")
                    continue
                
                # Add file data
                file_data.append({
                    "path": file_path,
                    "content": content,
                    "repository": repo_name,
                    "url": repo_url,
                    "commit": commit,
                    "branch": branch
                })
            
            # If no files with content, return success
            if not file_data:
                return {
                    "status": "success",
                    "files_processed": 0,
                    "message": "No file content to process"
                }
            
            # Send files to code parser agent
            parser_input = {
                "files": file_data,
                "repository": repo_name,
                "url": repo_url,
                "commit": commit,
                "branch": branch,
                "is_full_indexing": is_full_indexing
            }
            
            # Call code parser agent
            tool_response = wrapper.context.get_tool("code_parser_agent")
            if not tool_response.status.is_success():
                return {
                    "status": "error",
                    "message": f"Failed to get code parser agent: {tool_response.status.message}"
                }
            
            parser_agent = tool_response.tool
            response = parser_agent.run(parser_input)
            
            if not isinstance(response, ToolResponse) or not response.status.is_success():
                return {
                    "status": "error",
                    "message": f"Failed to parse files: {response.status.message if isinstance(response, ToolResponse) else 'Unknown error'}"
                }
            
            # Return success
            return {
                "status": "success",
                "files_processed": len(file_data),
                "message": "Files processed successfully"
            }
            
        except Exception as e:
            wrapper.logger.error(f"Error processing file batch: {e}")
            return {
                "status": "error",
                "message": f"Error processing file batch: {str(e)}"
            }
    
    def _load_commit_history(self, wrapper) -> None:
        """
        Load commit history from file.
        
        Args:
            wrapper: Agent wrapper with state
        """
        try:
            if os.path.exists(wrapper.commit_history_file):
                with open(wrapper.commit_history_file, "r") as f:
                    wrapper.commit_history = json.load(f)
                wrapper.logger.info(f"Loaded commit history for {len(wrapper.commit_history)} repositories")
        except Exception as e:
            wrapper.logger.error(f"Failed to load commit history: {e}")
            wrapper.commit_history = {}
    
    def _save_commit_history(self, wrapper) -> None:
        """
        Save commit history to file.
        
        Args:
            wrapper: Agent wrapper with state
        """
        try:
            with open(wrapper.commit_history_file, "w") as f:
                json.dump(wrapper.commit_history, f)
            wrapper.logger.info(f"Saved commit history for {len(wrapper.commit_history)} repositories")
        except Exception as e:
            wrapper.logger.error(f"Failed to save commit history: {e}")
    
    def poll_repositories(self) -> None:
        """Poll repositories for changes."""
        # Get wrapper for this agent
        wrapper = self.get_wrapper()
        
        wrapper.logger.info(f"Polling repositories (interval: {wrapper.polling_interval}s)")
        
        while True:
            # Process repositories
            self.run(wrapper, {"repositories": wrapper.repositories})
            
            # Sleep until next poll
            wrapper.logger.info(f"Sleeping for {wrapper.polling_interval} seconds")
            time.sleep(wrapper.polling_interval)