"""
Git Tool

Tool for Git operations and code extraction.
"""

import os
import logging
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Set
from pathlib import Path
import git
from git import Repo, Git


class GitTool:
    """
    Tool for Git operations and code extraction.
    
    This tool handles repository cloning, change detection, and file content extraction.
    It's a core component for the incremental indexing system.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Git tool.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("git_tool")
        
        # Configure defaults
        self.workspace_dir = config.get("workspace_dir", "./workspace")
        self.ignored_extensions = set(config.get("ignored_extensions", [
            ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".pdf", 
            ".zip", ".tar", ".gz", ".tgz", ".rar", ".jar", ".war",
            ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv"
        ]))
        self.ignored_dirs = set(config.get("ignored_dirs", [
            ".git", "__pycache__", "node_modules", "venv", "env", ".venv", ".env",
            "dist", "build", "target", "bin", "obj", ".idea", ".vscode"
        ]))
        self.max_file_size = config.get("max_file_size", 1024 * 1024)  # 1MB
        
        # SSH Authentication settings
        self.use_ssh = config.get("use_ssh", False)
        self.ssh_key_path = config.get("ssh_key_path") or os.environ.get("CODEINDEXER_SSH_KEY")
        
        # Configure SSH environment if using SSH authentication
        if self.use_ssh:
            # Build SSH command based on available key information
            ssh_command = 'ssh -o StrictHostKeyChecking=no'
            
            if self.ssh_key_path:
                if os.path.exists(self.ssh_key_path):
                    ssh_command += f' -i {self.ssh_key_path}'
                    self.logger.info(f"Using custom SSH key: {self.ssh_key_path}")
                else:
                    self.logger.warning(f"Specified SSH key does not exist: {self.ssh_key_path}")
            
            os.environ['GIT_SSH_COMMAND'] = ssh_command
            self.logger.info("SSH authentication enabled for Git operations")
        
        # Ensure workspace directory exists
        os.makedirs(self.workspace_dir, exist_ok=True)
    
    def clone_repository(self, repo_url: str, branch: str = "main", 
                       repo_dir: Optional[str] = None) -> Tuple[bool, str]:
        """
        Clone a Git repository.
        
        Args:
            repo_url: URL of the repository
            branch: Branch to clone
            repo_dir: Directory to clone into (optional)
            
        Returns:
            Tuple of (success, repo_path)
        """
        try:
            # Generate a repo directory name from the URL if not provided
            if not repo_dir:
                repo_name = repo_url.split("/")[-1].replace(".git", "")
                repo_dir = os.path.join(self.workspace_dir, repo_name)
            
            # Convert HTTPS URL to SSH URL if SSH authentication is enabled
            original_url = repo_url
            if self.use_ssh and repo_url.startswith(('http://', 'https://')):
                # Extract domain and path from HTTPS URL
                url_parts = repo_url.replace('http://', '').replace('https://', '').split('/', 1)
                if len(url_parts) == 2:
                    domain = url_parts[0]
                    path = url_parts[1]
                    
                    # Remove .git suffix if present for consistency
                    if path.endswith('.git'):
                        path = path[:-4]
                    
                    # Transform to SSH format: git@domain:path.git
                    repo_url = f"git@{domain}:{path}.git"
                    self.logger.info(f"Using SSH authentication, converted URL from {original_url} to: {repo_url}")
            
            self.logger.info(f"Repository dir: {repo_dir}")
            
            # Ensure the workspace directory exists
            os.makedirs(self.workspace_dir, exist_ok=True)
            
            # Check if repo already exists
            if os.path.exists(repo_dir):
                self.logger.info(f"Repository already exists at {repo_dir}")
                try:
                    repo = Repo(repo_dir)
                    
                    # Fetch latest changes
                    self.logger.info(f"Fetching latest changes from {repo_url}")
                    for remote in repo.remotes:
                        self.logger.info(f"Fetching from remote: {remote.name}")
                        remote.fetch()
                    
                    # Checkout the specified branch
                    self.logger.info(f"Checking out branch {branch}")
                    repo.git.checkout(branch)
                    
                    # Pull latest changes
                    self.logger.info(f"Pulling latest changes")
                    repo.git.pull()
                    
                    return True, repo_dir
                except Exception as inner_e:
                    self.logger.error(f"Error updating existing repository: {inner_e}")
                    # If updating fails, try fresh clone after removing
                    import shutil
                    self.logger.info(f"Removing {repo_dir} for fresh clone")
                    shutil.rmtree(repo_dir, ignore_errors=True)
            
            # Clone the repository
            self.logger.info(f"Cloning repository {repo_url} to {repo_dir}")
            repo = Repo.clone_from(repo_url, repo_dir, branch=branch)
            
            self.logger.info(f"Repository cloned successfully to {repo_dir}")
            return True, repo_dir
            
        except git.exc.GitCommandError as e:
            # Provide more helpful error messages for authentication issues
            error_msg = str(e)
            if "Permission denied (publickey)" in error_msg:
                self.logger.error("SSH authentication failed: Permission denied. Ensure your SSH key is properly set up and added to your SSH agent.")
            elif "The requested URL returned error: 403" in error_msg:
                if self.use_ssh:
                    self.logger.error("Authentication failed despite SSH being enabled. Check if the SSH URL conversion is correct and your SSH key has access to this repository.")
                else:
                    self.logger.error("Authentication failed: Repository requires authentication. Try using --ssh-auth flag or providing credentials.")
            else:
                self.logger.error(f"Failed to clone repository: {e}")
            
            import traceback
            self.logger.error(traceback.format_exc())
            return False, ""
        except Exception as e:
            self.logger.error(f"Failed to clone repository: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False, ""
    
    def get_changed_files(self, repo_path: str, base_commit: Optional[str] = None, 
                        head_commit: str = "HEAD") -> Dict[str, str]:
        """
        Get files that changed between two commits.
        
        Args:
            repo_path: Path to the repository
            base_commit: Base commit hash (if None, will use the previous commit)
            head_commit: Head commit hash
            
        Returns:
            Dictionary mapping file paths to change types (A=Added, M=Modified, D=Deleted)
        """
        try:
            repo = Repo(repo_path)
            
            # If base_commit is not provided, use HEAD~1
            if not base_commit:
                # Handle the case of initial commit
                if len(list(repo.iter_commits())) <= 1:
                    # For initial commit, get all files
                    changes = {}
                    for file_path in repo.git.ls_files().splitlines():
                        changes[file_path] = "A"  # Mark as added
                    return changes
                else:
                    base_commit = "HEAD~1"
            
            # Check if base_commit exists in this repository
            try:
                # Try to get the commit object to verify it exists
                repo.commit(base_commit)
            except Exception as commit_error:
                self.logger.warning(f"Base commit {base_commit} not found in repository: {commit_error}")
                self.logger.info("Falling back to full indexing by returning all files")
                
                # Return all files as "Added" to trigger full indexing
                changes = {}
                for file_path in repo.git.ls_files().splitlines():
                    changes[file_path] = "A"  # Mark as added
                return changes
            
            # Get diff between commits
            try:
                diff_index = repo.git.diff("--name-status", base_commit, head_commit)
            except Exception as diff_error:
                self.logger.warning(f"Failed to compare commits {base_commit} and {head_commit}: {diff_error}")
                self.logger.info("Falling back to full indexing by returning all files")
                
                # Return all files as "Added" to trigger full indexing
                changes = {}
                for file_path in repo.git.ls_files().splitlines():
                    changes[file_path] = "A"  # Mark as added
                return changes
            
            # Parse the diff output
            changes = {}
            for line in diff_index.splitlines():
                if not line.strip():
                    continue
                    
                parts = line.split()
                if len(parts) < 2:
                    continue
                    
                change_type = parts[0]
                file_path = " ".join(parts[1:])  # Handle filenames with spaces
                
                # Normalize change type
                if change_type.startswith("A"):
                    change_type = "A"  # Added
                elif change_type.startswith("M"):
                    change_type = "M"  # Modified
                elif change_type.startswith("D"):
                    change_type = "D"  # Deleted
                elif change_type.startswith("R"):
                    change_type = "R"  # Renamed
                    # For renamed files, the format is: R{similarity} old-path new-path
                    # We need to extract both paths
                    # For simplicity, just treat it as a modified file for now
                    change_type = "M"
                
                changes[file_path] = change_type
            
            return changes
            
        except Exception as e:
            self.logger.error(f"Failed to get changed files: {e}")
            # Return all files to ensure processing continues
            try:
                repo = Repo(repo_path)
                changes = {}
                for file_path in repo.git.ls_files().splitlines():
                    changes[file_path] = "A"  # Mark as added
                self.logger.info(f"Falling back to full indexing with {len(changes)} files")
                return changes
            except Exception as inner_e:
                self.logger.error(f"Failed to get file list for fallback: {inner_e}")
                return {}
    
    def get_file_content(self, repo_path: str, file_path: str, 
                       commit: str = "HEAD") -> Optional[str]:
        """
        Get content of a file at a specific commit.
        
        Args:
            repo_path: Path to the repository
            file_path: Path to the file within the repository
            commit: Commit hash
            
        Returns:
            File content as string, or None if file not found
        """
        try:
            repo = Repo(repo_path)
            
            # Check if file exists in the repository
            full_path = os.path.join(repo_path, file_path)
            if not (os.path.isfile(full_path) or commit != "HEAD"):
                self.logger.warning(f"File {file_path} not found in repository")
                return None
            
            # Get file content at the specified commit
            try:
                content = repo.git.show(f"{commit}:{file_path}")
                return content
            except git.exc.GitCommandError:
                self.logger.warning(f"File {file_path} not found at commit {commit}")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to get file content: {e}")
            return None
    
    def filter_indexable_files(self, repo_path: str, file_paths: List[str]) -> List[str]:
        """
        Filter files that should be indexed.
        
        Args:
            repo_path: Path to the repository
            file_paths: List of file paths to filter
            
        Returns:
            List of indexable file paths
        """
        indexable_files = []
        
        for file_path in file_paths:
            # Skip files with ignored extensions
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self.ignored_extensions:
                continue
            
            # Skip files in ignored directories
            path_parts = Path(file_path).parts
            if any(part in self.ignored_dirs for part in path_parts):
                continue
            
            # Check file size
            full_path = os.path.join(repo_path, file_path)
            if os.path.isfile(full_path) and os.path.getsize(full_path) > self.max_file_size:
                self.logger.info(f"Skipping large file: {file_path}")
                continue
            
            indexable_files.append(file_path)
        
        return indexable_files
    
    def get_commit_info(self, repo_path: str, commit: str = "HEAD") -> Dict[str, Any]:
        """
        Get information about a commit.
        
        Args:
            repo_path: Path to the repository
            commit: Commit hash
            
        Returns:
            Dictionary with commit information
        """
        try:
            repo = Repo(repo_path)
            commit_obj = repo.commit(commit)
            
            return {
                "hash": commit_obj.hexsha,
                "short_hash": commit_obj.hexsha[:7],
                "author": commit_obj.author.name,
                "author_email": commit_obj.author.email,
                "date": commit_obj.committed_datetime.isoformat(),
                "message": commit_obj.message,
                "stats": {
                    "files": len(commit_obj.stats.files),
                    "insertions": commit_obj.stats.total["insertions"],
                    "deletions": commit_obj.stats.total["deletions"],
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get commit info: {e}")
            return {}
    
    def create_repository_snapshot(self, repo_path: str, 
                                 commit: str = "HEAD") -> Tuple[bool, str]:
        """
        Create a snapshot of the repository at a specific commit.
        
        Args:
            repo_path: Path to the repository
            commit: Commit hash
            
        Returns:
            Tuple of (success, snapshot_path)
        """
        try:
            repo = Repo(repo_path)
            
            # Create a temporary directory for the snapshot
            snapshot_dir = tempfile.mkdtemp(prefix="repo_snapshot_")
            
            # Save the repository state to the snapshot directory
            repo.git.checkout(commit)
            
            # Copy all files to the snapshot directory (excluding .git)
            for root, dirs, files in os.walk(repo_path):
                # Skip .git directory
                if ".git" in dirs:
                    dirs.remove(".git")
                
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, repo_path)
                    dst_path = os.path.join(snapshot_dir, rel_path)
                    
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    
                    # Copy file
                    with open(src_path, "rb") as src, open(dst_path, "wb") as dst:
                        dst.write(src.read())
            
            self.logger.info(f"Repository snapshot created at {snapshot_dir}")
            return True, snapshot_dir
            
        except Exception as e:
            self.logger.error(f"Failed to create repository snapshot: {e}")
            return False, ""