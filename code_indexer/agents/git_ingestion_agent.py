"""
Git Ingestion Agent

This agent monitors Git repositories, detects changes, and extracts code files.
"""

import os
import logging
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from google.adk import Agent, AgentContext
from google.adk.tooling import BaseTool
from code_indexer.tools.git_tool import GitTool
from code_indexer.utils.repo_utils import get_file_hash


class GitIngestionAgent(Agent):
    """
    Agent responsible for monitoring repositories and detecting code changes.
    
    This agent watches Git repositories, detects changes since the last indexing,
    and prepares the files that need to be processed by downstream agents.
    """
    
    def __init__(self):
        """Initialize the Git Ingestion Agent."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def initialize(self, context: AgentContext) -> None:
        """
        Initialize the agent with necessary tools and state.
        
        Args:
            context: The agent context
        """
        self.context = context
        
        # Initialize the Git tool
        self.git_tool = GitTool()
        
        # Initialize state
        if "indexed_repos" not in context.state:
            context.state["indexed_repos"] = {}
    
    def process_repository(self, repo_url: str, branch: str = "main") -> Dict[str, Any]:
        """
        Fetch repository and detect changes since last indexing.
        
        Args:
            repo_url: The URL of the Git repository
            branch: The branch to process (default: "main")
            
        Returns:
            Dictionary containing repository information and changed files
        """
        self.logger.info(f"Processing repository: {repo_url} (branch: {branch})")
        
        # Create a unique repo key for storage
        repo_key = self._make_repo_key(repo_url, branch)
        
        # Get last indexed commit, if any
        last_indexed = self.context.state["indexed_repos"].get(repo_key, {})
        last_commit = last_indexed.get("last_commit_sha", None)
        
        # Clone or update repository
        repo_path = self.git_tool.fetch_repository(repo_url, branch)
        
        # Get current HEAD commit
        current_commit = self.git_tool.get_current_commit(repo_path)
        
        # Get changed files
        if last_commit:
            diff_files = self.git_tool.get_changed_files(repo_path, last_commit, current_commit)
            self.logger.info(f"Found {len(diff_files['added'])} added/modified files and "
                            f"{len(diff_files['deleted'])} deleted files since last indexing")
        else:
            # First time indexing, get all files
            self.logger.info("First-time indexing, processing all files")
            all_files = self.git_tool.get_all_files(repo_path)
            diff_files = {
                "added": all_files,
                "deleted": []
            }
        
        # Update indexed state
        self.context.state["indexed_repos"][repo_key] = {
            "repo_url": repo_url,
            "branch": branch,
            "last_commit_sha": current_commit,
            "last_indexed_at": datetime.now().isoformat()
        }
        
        # Prepare result
        result = {
            "repo_url": repo_url,
            "branch": branch,
            "repo_path": repo_path,
            "current_commit": current_commit,
            "last_commit": last_commit,
            "added_files": diff_files["added"],
            "deleted_files": diff_files["deleted"],
            "is_first_indexing": last_commit is None
        }
        
        return result
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the Git ingestion process.
        
        Args:
            inputs: Dictionary with "repo_url" and optional "branch"
            
        Returns:
            Dictionary with repository and changed files information
        """
        # Extract inputs
        repo_url = inputs.get("repo_url")
        branch = inputs.get("branch", "main")
        
        if not repo_url:
            raise ValueError("Repository URL is required")
        
        # Process repository
        result = self.process_repository(repo_url, branch)
        
        # Return the changed files and repository information
        return result
    
    def _make_repo_key(self, repo_url: str, branch: str) -> str:
        """
        Create a unique key for a repository and branch.
        
        Args:
            repo_url: Repository URL
            branch: Branch name
            
        Returns:
            A unique key string
        """
        return f"{repo_url}#{branch}"