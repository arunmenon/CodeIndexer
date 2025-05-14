"""
Git Ingestion Stage

This module handles repository cloning and file extraction.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

# Import the GitTool from the codebase
from code_indexer.tools.git_tool import GitTool

# Configure logging
logging.basicConfig(level=logging.INFO,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ingestion_git")


def process_git_repository(repository_url: str, branch: str = "main", 
                         mode: str = "incremental", force_reindex: bool = False,
                         output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Process a git repository to extract file contents.
    
    Args:
        repository_url: URL or path to the repository
        branch: Branch to process
        mode: "incremental" or "full" ingestion mode
        force_reindex: Whether to force reindexing
        output_file: Path to save output (optional)
        
    Returns:
        Dictionary with processing results
    """
    logger.info(f"Processing repository: {repository_url}")
    
    try:
        # Create git tool
        git_tool = GitTool({
            "workspace_dir": "./workspace"
        })
        
        # Clone or update repository
        success, repo_path = git_tool.clone_repository(repository_url, branch)
        if not success:
            return {
                "status": "error",
                "message": f"Failed to clone repository: {repository_url}"
            }
        
        # Get latest commit
        latest_commit_info = git_tool.get_commit_info(repo_path)
        if not latest_commit_info:
            return {
                "status": "error",
                "message": "Failed to get latest commit information"
            }
        
        latest_commit = latest_commit_info["hash"]
        
        # Determine repository name
        repo_name = os.path.basename(repository_url.rstrip("/").replace(".git", ""))
        
        # Get changed files
        if mode == "full" or force_reindex:
            # Full indexing - get all files
            all_files = []
            for root, _, files in os.walk(repo_path):
                if ".git" in root:
                    continue
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    all_files.append(rel_path)
            
            changed_files = all_files
            is_full_indexing = True
        else:
            # Incremental indexing
            # Load commit history to find last indexed commit
            commit_history_file = "commit_history.json"
            commit_history = {}
            
            if os.path.exists(commit_history_file):
                with open(commit_history_file, "r") as f:
                    commit_history = json.load(f)
            
            last_indexed_commit = commit_history.get(repository_url)
            
            if not last_indexed_commit:
                # No previous indexing, treat as full
                all_files = []
                for root, _, files in os.walk(repo_path):
                    if ".git" in root:
                        continue
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_path)
                        all_files.append(rel_path)
                
                changed_files = all_files
                is_full_indexing = True
            else:
                # Get changed files since last indexed commit
                changed_files_map = git_tool.get_changed_files(
                    repo_path, base_commit=last_indexed_commit, head_commit=latest_commit
                )
                
                # Filter out deleted files
                changed_files = [
                    file_path for file_path, change_type in changed_files_map.items()
                    if change_type != "D"  # Skip deleted files
                ]
                
                is_full_indexing = False
            
            # Update commit history
            commit_history[repository_url] = latest_commit
            with open(commit_history_file, "w") as f:
                json.dump(commit_history, f)
        
        # Filter indexable files
        indexable_files = git_tool.filter_indexable_files(repo_path, changed_files)
        
        if not indexable_files:
            logger.info("No files to index")
            return {
                "status": "success",
                "repository": repo_name,
                "url": repository_url,
                "commit": latest_commit,
                "branch": branch,
                "is_full_indexing": is_full_indexing,
                "files_detected": 0,
                "files_processed": 0,
                "file_data": []
            }
        
        # Process files
        file_data = []
        
        for file_path in indexable_files:
            # Get file content
            content = git_tool.get_file_content(repo_path, file_path, latest_commit)
            if content is None:
                logger.warning(f"Failed to get content for file {file_path}")
                continue
            
            # Add file data
            file_data.append({
                "path": file_path,
                "content": content,
                "repository": repo_name,
                "url": repository_url,
                "commit": latest_commit,
                "branch": branch
            })
        
        result = {
            "status": "success",
            "repository": repo_name,
            "url": repository_url,
            "commit": latest_commit,
            "branch": branch,
            "is_full_indexing": is_full_indexing,
            "files_detected": len(indexable_files),
            "files_processed": len(file_data),
            "file_data": file_data
        }
        
        # Save output if requested
        if output_file:
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Saved output to {output_file}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing git repository: {e}")
        return {
            "status": "error",
            "message": str(e)
        }