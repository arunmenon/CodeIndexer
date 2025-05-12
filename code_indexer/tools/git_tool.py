"""
Git Tool

Tool for interacting with Git repositories and extracting code changes.
"""

import os
import logging
import subprocess
import tempfile
import shutil
import hashlib
from typing import Dict, List, Optional, Any, Tuple

from google.adk.tooling import BaseTool


class GitTool(BaseTool):
    """
    Tool for Git operations and code extraction.
    
    Provides functionality to clone repositories, detect changes,
    and extract file content from Git repositories.
    """
    
    def __init__(self):
        """Initialize the Git tool."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.repo_cache = {}  # Path cache for repos we've already cloned
    
    def fetch_repository(self, repo_url: str, branch: str = "main") -> str:
        """
        Clone or update a Git repository.
        
        Args:
            repo_url: URL of the Git repository
            branch: Branch to clone or update (default: "main")
            
        Returns:
            Path to the local repository
        
        Raises:
            Exception: If Git operations fail
        """
        # Generate a unique directory name based on the repo URL
        repo_hash = hashlib.md5(repo_url.encode()).hexdigest()
        cache_key = f"{repo_hash}_{branch}"
        
        # Check if we've already cloned this repo
        if cache_key in self.repo_cache:
            repo_path = self.repo_cache[cache_key]
            self.logger.info(f"Using cached repository at {repo_path}")
            
            # Update the repository
            self._run_git_command(["fetch", "origin"], repo_path)
            self._run_git_command(["checkout", branch], repo_path)
            self._run_git_command(["pull", "origin", branch], repo_path)
            
            return repo_path
        
        # Clone the repository
        repo_dir = os.path.join(tempfile.gettempdir(), f"code_indexer_{repo_hash}")
        
        # Create or clean directory
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        os.makedirs(repo_dir)
        
        # Clone the repository
        self.logger.info(f"Cloning repository {repo_url} (branch: {branch}) to {repo_dir}")
        self._run_git_command(["clone", "--branch", branch, repo_url, repo_dir])
        
        # Cache the repository path
        self.repo_cache[cache_key] = repo_dir
        
        return repo_dir
    
    def get_current_commit(self, repo_path: str) -> str:
        """
        Get the current commit SHA of the repository.
        
        Args:
            repo_path: Path to the local repository
            
        Returns:
            Current commit SHA
        """
        result = self._run_git_command(["rev-parse", "HEAD"], repo_path)
        return result.strip()
    
    def get_changed_files(self, repo_path: str, from_commit: str, to_commit: str = "HEAD") -> Dict[str, List[str]]:
        """
        Get files changed between two commits.
        
        Args:
            repo_path: Path to the local repository
            from_commit: Starting commit SHA
            to_commit: Ending commit SHA (default: "HEAD")
            
        Returns:
            Dictionary with "added" and "deleted" file lists
        """
        # Get diff with name status
        diff_output = self._run_git_command(
            ["diff", "--name-status", f"{from_commit}..{to_commit}"], 
            repo_path
        )
        
        added_files = []
        deleted_files = []
        
        # Parse diff output
        for line in diff_output.splitlines():
            if not line.strip():
                continue
                
            parts = line.split()
            if len(parts) < 2:
                continue
                
            status = parts[0]
            file_path = parts[1]
            
            # Full path to the file
            full_path = os.path.join(repo_path, file_path)
            
            if status == "D":
                deleted_files.append(file_path)
            else:  # A, M, R, etc.
                added_files.append(file_path)
        
        return {
            "added": added_files,
            "deleted": deleted_files
        }
    
    def get_all_files(self, repo_path: str) -> List[str]:
        """
        Get all files in the repository.
        
        Args:
            repo_path: Path to the local repository
            
        Returns:
            List of all file paths in the repository
        """
        ls_output = self._run_git_command(["ls-files"], repo_path)
        
        files = []
        for line in ls_output.splitlines():
            if line.strip():
                files.append(line.strip())
        
        return files
    
    def get_file_content(self, repo_path: str, file_path: str, commit: str = "HEAD") -> str:
        """
        Get content of a file at a specific commit.
        
        Args:
            repo_path: Path to the local repository
            file_path: Path to the file within the repository
            commit: Commit SHA (default: "HEAD")
            
        Returns:
            Content of the file as string
        """
        try:
            content = self._run_git_command(["show", f"{commit}:{file_path}"], repo_path)
            return content
        except Exception as e:
            self.logger.error(f"Error getting file content: {e}")
            raise
    
    def _run_git_command(self, args: List[str], cwd: Optional[str] = None) -> str:
        """
        Run a Git command and return the output.
        
        Args:
            args: Git command arguments
            cwd: Working directory for the command
            
        Returns:
            Command output as string
            
        Raises:
            Exception: If the command fails
        """
        cmd = ["git"] + args
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {e.stderr}")
            raise Exception(f"Git command failed: {e.stderr}")