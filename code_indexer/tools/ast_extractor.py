"""
AST Extractor Tool

Provides a unified interface for extracting Abstract Syntax Trees (ASTs) from
code in different programming languages.
"""

import os
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

# Import our standalone Tree-Sitter parser
from code_indexer.tools.tree_sitter_parser import TreeSitterParser

# Configure logging
logger = logging.getLogger(__name__)

class ASTExtractor:
    """
    Unified AST extraction for multiple languages.
    
    This class serves as the main entry point for AST extraction, using the 
    decoupled Tree-Sitter parser underneath.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the AST extractor.
        
        Args:
            config: Configuration dictionary with optional settings:
                   - languages: List of languages to support
        """
        self.config = config or {}
        
        # Initialize Tree-Sitter parser
        languages = self.config.get("languages")
        try:
            self.parser = TreeSitterParser(languages)
            logger.info(f"Tree-sitter parser initialized with languages: {self.parser.get_supported_languages()}")
        except ImportError as e:
            logger.error(f"Failed to initialize Tree-sitter parser: {e}")
            raise
        
        # Language detection settings - using expanded list from main branch
        self.language_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "c_sharp",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".rs": "rust"
        }
    
    def extract_ast(self, code: str, language: Optional[str] = None, 
                  file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract AST from code.
        
        Args:
            code: Source code
            language: Programming language (optional, will be detected if not provided)
            file_path: Path to the source file (optional, used for language detection)
            
        Returns:
            Dictionary containing the AST in a standardized format
        """
        # Detect language if not provided
        if not language and file_path:
            language = self.parser.detect_language(file_path)
        
        if not language:
            # Try to detect from code if still no language (taking from main branch)
            language = self._detect_language_from_code(code)
            logger.info(f"Detected language from code: {language}")
            
        # Parse code using tree-sitter
        ast_dict = self.parser.parse_string(code, language)
        
        # Add file path if provided
        if file_path:
            ast_dict["file_path"] = file_path
        
        return ast_dict
    
    def extract_ast_from_file(self, file_path: Union[str, Path], 
                            language: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract AST from a file.
        
        Args:
            file_path: Path to the source file
            language: Programming language (optional, will be detected if not provided)
            
        Returns:
            Dictionary containing the AST in a standardized format
        """
        # Convert to string for consistency
        file_path_str = str(file_path)
        
        # Detect language if not provided
        if not language:
            language = self._detect_language(file_path_str)
        
        # Use tree-sitter parser to parse file
        try:
            ast_dict = self.parser.parse_file(file_path_str, language)
            return ast_dict
        except Exception as e:
            logger.error(f"Failed to extract AST from file {file_path}: {e}")
            return {
                "error": str(e),
                "file_path": file_path_str,
                "language": language or "unknown"
            }
    
    def _detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file path.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Detected language or None
        """
        ext = os.path.splitext(file_path)[1].lower()
        return self.language_extensions.get(ext)
    
    def _detect_language_from_code(self, code: str) -> str:
        """
        Attempt to detect programming language from code content.
        
        Args:
            code: Source code
            
        Returns:
            Detected language or 'unknown'
        """
        # Simple heuristics to detect language
        if code.strip().startswith("<?php"):
            return "php"
        elif "function" in code and ("{" in code and "}" in code) and (";" in code):
            return "javascript"
        elif "def " in code and ":" in code and "import " in code:
            return "python"
        elif "class " in code and "{" in code and "public" in code and ";" in code:
            return "java"
        elif "package " in code and "import" in code and "func " in code:
            return "go"
        
        # Default to unknown
        return "unknown"


def create_ast_extractor(config: Dict[str, Any] = None) -> ASTExtractor:
    """
    Create an AST extractor with the given configuration.
    
    This factory function is provided for backward compatibility.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured ASTExtractor instance
    """
    return ASTExtractor(config)