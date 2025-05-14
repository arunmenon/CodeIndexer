"""
Direct Git Ingestion Runner

A standalone implementation of the Git ingestion process without ADK dependencies.
"""

import logging
import json
import os
import time
from typing import Dict, Any, List, Optional, Set, Tuple
import hashlib
from pathlib import Path

# Import the GitTool from the codebase
from code_indexer.tools.git_tool import GitTool


class DirectGitIngestionRunner:
    """
    DirectGitIngestionRunner is responsible for monitoring repositories and detecting code changes.
    
    This is a direct runner implementation that doesn't depend on ADK but provides
    the same functionality as the GitIngestionAgent.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the runner.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger("direct_git_ingestion")
        
        # Configure defaults from config dictionary
        self.repositories = self.config.get('repositories', [])
        self.default_branch = self.config.get('default_branch', 'main')
        self.polling_interval = self.config.get('polling_interval', 3600)  # 1 hour
        self.commit_history_file = self.config.get('commit_history_file', 'commit_history.json')
        self.max_file_batch = self.config.get('max_file_batch', 100)
        
        # State
        self.commit_history = {}  # repository_url -> last_indexed_commit
        
        # Initialize the GitTool
        self.git_tool = GitTool(self.config.get('git_tool_config', {}))
        
        # Load commit history
        self._load_commit_history()
    
    def run(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run the git ingestion process.
        
        Args:
            input_data: Dictionary containing input parameters
            
        Returns:
            Dictionary with detection results
        """
        self.logger.info("Starting direct Git ingestion")
        
        input_data = input_data or {}
        
        # Extract parameters from input
        repositories = input_data.get("repositories", self.repositories)
        if not repositories:
            return {"error": "No repositories specified"}
        
        mode = input_data.get("mode", "incremental")  # incremental or full
        force_reindex = input_data.get("force_reindex", False)
        
        # Process each repository
        processing_results = []
        
        for repo_config in repositories:
            # Extract repository information
            repo_url = repo_config.get("url", "")
            branch = repo_config.get("branch", self.default_branch)
            repo_name = repo_config.get("name", repo_url.split("/")[-1].replace(".git", ""))
            
            if not repo_url:
                self.logger.warning("Repository URL not specified, skipping")
                continue
            
            # Process repository
            repo_result = self._process_repository(
                repo_url=repo_url, 
                branch=branch,
                repo_name=repo_name,
                mode=mode,
                force_reindex=force_reindex
            )
            
            processing_results.append(repo_result)
        
        # Save commit history
        self._save_commit_history()
        
        return {
            "results": processing_results,
            "repositories_processed": len(processing_results)
        }
    
    def _process_repository(self, repo_url: str, branch: str, repo_name: str,
                         mode: str, force_reindex: bool) -> Dict[str, Any]:
        """
        Process a single repository.
        
        Args:
            repo_url: Repository URL
            branch: Branch to process
            repo_name: Repository name
            mode: Processing mode (incremental or full)
            force_reindex: Whether to force reindexing
            
        Returns:
            Dictionary with processing results
        """
        self.logger.info(f"Processing repository {repo_name} ({repo_url})")
        
        # Clone or update repository
        success, repo_path = self.git_tool.clone_repository(repo_url, branch)
        if not success:
            return {
                "repository": repo_name,
                "url": repo_url,
                "status": "error",
                "message": "Failed to clone repository"
            }
        
        # Get latest commit
        latest_commit_info = self.git_tool.get_commit_info(repo_path)
        if not latest_commit_info:
            return {
                "repository": repo_name,
                "url": repo_url,
                "status": "error",
                "message": "Failed to get latest commit information"
            }
        
        latest_commit = latest_commit_info["hash"]
        
        # Get last indexed commit
        last_indexed_commit = self.commit_history.get(repo_url)
        
        # Check if reindexing is needed
        if mode == "full" or force_reindex or not last_indexed_commit:
            # Full indexing
            changed_files = self._get_all_files(repo_path)
            is_full_indexing = True
        else:
            # Incremental indexing
            changed_files_map = self.git_tool.get_changed_files(
                repo_path, base_commit=last_indexed_commit, head_commit=latest_commit
            )
            
            # Filter out deleted files
            changed_files = [
                file_path for file_path, change_type in changed_files_map.items()
                if change_type != "D"  # Skip deleted files
            ]
            
            is_full_indexing = False
        
        # Filter indexable files
        indexable_files = self.git_tool.filter_indexable_files(repo_path, changed_files)
        
        # Update commit history
        self.commit_history[repo_url] = latest_commit
        
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
        file_batches = self._create_file_batches(indexable_files)
        
        # Prepare file data for all batches
        all_file_data = []
        for batch in file_batches:
            for file_path in batch:
                # Get file content
                content = self.git_tool.get_file_content(repo_path, file_path, latest_commit)
                if content is None:
                    self.logger.warning(f"Failed to get content for file {file_path}")
                    continue
                
                # Add file data
                all_file_data.append({
                    "path": file_path,
                    "content": content,
                    "repository": repo_name,
                    "url": repo_url,
                    "commit": latest_commit,
                    "branch": branch
                })
        
        return {
            "repository": repo_name,
            "url": repo_url,
            "status": "success",
            "indexing_type": "full" if is_full_indexing else "incremental",
            "commit": latest_commit,
            "files_detected": len(indexable_files),
            "files_processed": len(all_file_data),
            "message": f"Processed {len(all_file_data)} files",
            "file_data": all_file_data,  # Return the processed file data for the next step
            "is_full_indexing": is_full_indexing
        }
    
    def _get_all_files(self, repo_path: str) -> List[str]:
        """
        Get all files in a repository.
        
        Args:
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
    
    def _create_file_batches(self, files: List[str]) -> List[List[str]]:
        """
        Create batches of files for processing.
        
        Args:
            files: List of file paths
            
        Returns:
            List of file path batches
        """
        batches = []
        for i in range(0, len(files), self.max_file_batch):
            batches.append(files[i:i + self.max_file_batch])
        return batches
    
    def _load_commit_history(self) -> None:
        """
        Load commit history from file.
        """
        try:
            if os.path.exists(self.commit_history_file):
                with open(self.commit_history_file, "r") as f:
                    self.commit_history = json.load(f)
                self.logger.info(f"Loaded commit history for {len(self.commit_history)} repositories")
        except Exception as e:
            self.logger.error(f"Failed to load commit history: {e}")
            self.commit_history = {}
    
    def _save_commit_history(self) -> None:
        """
        Save commit history to file.
        """
        try:
            with open(self.commit_history_file, "w") as f:
                json.dump(self.commit_history, f)
            self.logger.info(f"Saved commit history for {len(self.commit_history)} repositories")
        except Exception as e:
            self.logger.error(f"Failed to save commit history: {e}")
    
    def poll_repositories(self) -> None:
        """Poll repositories for changes."""
        self.logger.info(f"Polling repositories (interval: {self.polling_interval}s)")
        
        while True:
            # Process repositories
            self.run({"repositories": self.repositories})
            
            # Sleep until next poll
            self.logger.info(f"Sleeping for {self.polling_interval} seconds")
            time.sleep(self.polling_interval)