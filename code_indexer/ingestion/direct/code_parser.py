"""
Direct Code Parser Runner

A standalone implementation of the code parser process without ADK dependencies.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

# Import the ASTExtractorTool from the codebase
from code_indexer.tools.ast_extractor import ASTExtractorTool


class DirectCodeParserRunner:
    """
    DirectCodeParserRunner is responsible for parsing source files into AST structures.
    
    This is a direct runner implementation that doesn't depend on ADK but provides
    the same functionality as the CodeParserAgent.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the runner.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger("direct_code_parser")
        
        # Configure defaults
        self.max_file_size = self.config.get("max_file_size", 1024 * 1024)  # 1MB
        self.batch_size = self.config.get("batch_size", 10)
        
        # Initialize the AST extractor tool
        self.ast_extractor = ASTExtractorTool(self.config.get("ast_extractor_config", {}))
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse source files into AST structures.
        
        Args:
            input_data: Dictionary containing files to parse
            
        Returns:
            Dictionary with parsing results
        """
        self.logger.info("Starting direct code parser")
        
        # Extract files from input
        files = input_data.get("file_data", [])
        if not files:
            return {"error": "No files to parse"}
        
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
        
        return {
            "files_parsed": len(parsed_files),
            "files_failed": len(failed_files),
            "failed_files": failed_files[:10],  # Include only the first 10 failed files
            "asts": parsed_files,
            "repository": repository,
            "repository_url": repository_url,
            "commit": commit,
            "branch": branch,
            "is_full_indexing": is_full_indexing
        }
    
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