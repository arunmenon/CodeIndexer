"""
Code Parser Agent

This agent is responsible for parsing source files and extracting AST representations.
"""

import os
import pathlib
import logging
import time
from typing import Dict, List, Any, Optional, Tuple

from google.adk import Agent, AgentContext
from google.adk.tooling import BaseTool

from code_indexer.tools.ast_extractor import ASTExtractorTool


class CodeParserAgent(Agent):
    """
    Agent responsible for parsing source files into AST structures.
    
    This agent takes files from GitIngestionAgent, determines their language,
    and uses the ASTExtractorTool to generate standardized AST representations.
    """
    
    def __init__(self):
        """Initialize the Code Parser Agent."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Language detection configuration
        self.ext_map = {
            ".java": "java",
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".ts": "typescript",  # if supported
        }
        
        # Max file size to parse (avoid binary files)
        self.max_file_size = 1024 * 1024  # 1MB
    
    def initialize(self, context: AgentContext) -> None:
        """
        Initialize the agent with necessary tools and state.
        
        Args:
            context: The agent context
        """
        self.context = context
        
        # Initialize the AST extractor tool
        self.ast_tool = ASTExtractorTool()
        
        # Load language overrides if configured
        self.lang_overrides = context.state.get("lang_overrides", {})
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and parse source files.
        
        Args:
            inputs: Dictionary containing repository information and files to process
            
        Returns:
            Dictionary with parsed files and their AST representations
        """
        # Extract inputs
        repo_path = inputs.get("repo_path")
        added_files = inputs.get("added_files", [])
        
        if not repo_path or not added_files:
            self.logger.warning("No repository path or files provided")
            return {
                "parsed_files": [],
                "skipped_files": [],
                "repo_path": repo_path
            }
        
        # Track progress and results
        parsed_files = []
        skipped_files = []
        
        # Process each file
        for file_path in added_files:
            full_path = os.path.join(repo_path, file_path)
            
            # Skip files that don't exist
            if not os.path.exists(full_path):
                self.logger.warning(f"File not found: {full_path}")
                skipped_files.append({
                    "path": file_path,
                    "reason": "file_not_found"
                })
                continue
            
            # Skip files that are too large
            if os.path.getsize(full_path) > self.max_file_size:
                self.logger.info(f"Skipping large file: {file_path}")
                skipped_files.append({
                    "path": file_path,
                    "reason": "file_too_large"
                })
                continue
            
            # Detect language
            language = self._detect_lang(file_path)
            
            if not language:
                self.logger.info(f"Skipping unsupported language: {file_path}")
                skipped_files.append({
                    "path": file_path,
                    "reason": "unsupported_language"
                })
                continue
            
            # Parse file with AST extractor
            try:
                start_time = time.time()
                ast_data = self.ast_tool.extract(full_path, language)
                
                # Generate a unique ID based on file path and content
                file_id = self._generate_file_id(file_path)
                
                # Find function calls
                calls = self.ast_tool.find_calls(ast_data, language)
                
                # Add to parsed files
                parsed_files.append({
                    "path": file_path,
                    "full_path": full_path,
                    "language": language,
                    "file_id": file_id,
                    "ast": ast_data,
                    "calls": calls,
                    "parse_time": time.time() - start_time
                })
                
                self.logger.info(f"Parsed {file_path} as {language}")
                
            except Exception as e:
                self.logger.error(f"Error parsing {file_path}: {e}")
                skipped_files.append({
                    "path": file_path,
                    "reason": "parse_error",
                    "error": str(e)
                })
        
        # Return results
        return {
            "parsed_files": parsed_files,
            "skipped_files": skipped_files,
            "repo_path": repo_path
        }
    
    def _detect_lang(self, path: str) -> Optional[str]:
        """
        Detect the programming language of a file.
        
        Args:
            path: Path to the file
            
        Returns:
            Language string or None if unsupported
        """
        # 1. Fast path: by extension
        ext = pathlib.Path(path).suffix.lower()
        if ext in self.ext_map:
            return self.ext_map[ext]
        
        # 2. Repository-specific overrides
        for prefix, lang in self.lang_overrides.items():
            if path.startswith(prefix):
                return lang
        
        # 3. Content sniff fallback
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    start = f.read(200).decode("utf-8", "ignore")
                
                # Check for Python shebang
                if start.startswith("#!") and "python" in start:
                    return "python"
                
                # Check for Java package/class patterns
                if "package " in start and "class " in start:
                    return "java"
                
                # Check for JavaScript patterns
                if "function " in start or "const " in start or "let " in start:
                    return "javascript"
            except Exception:
                pass
        
        # Unsupported language
        return None
    
    def _generate_file_id(self, file_path: str) -> str:
        """
        Generate a unique ID for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Unique ID string
        """
        import hashlib
        return hashlib.md5(file_path.encode()).hexdigest()