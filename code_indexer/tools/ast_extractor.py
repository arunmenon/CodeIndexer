"""
AST Extractor Tool

Provides a unified interface for extracting Abstract Syntax Trees (ASTs) from
code in different programming languages.
"""

import os
import ast
import logging
import json
import tempfile
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path


class ASTExtractorTool:
    """
    Unified AST extraction for multiple languages.
    
    Provides a consistent interface to extract ASTs from code files in different
    languages, returning a standardized JSON-serializable tree structure.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the AST extractor tool.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("ast_extractor_tool")
        
        # Language parsers
        self.python_parser = PythonParser()
        self.tree_sitter_parser = None
        
        # Load Tree-sitter if available and configured
        if config.get("use_tree_sitter", True):
            try:
                from .parsers.tree_sitter_parser import TreeSitterParser
                self.tree_sitter_parser = TreeSitterParser(config.get("tree_sitter_config", {}))
                self.logger.info("Tree-sitter parser initialized")
            except ImportError:
                self.logger.warning("Tree-sitter not available, falling back to built-in parsers")
        
        # Language detection settings
        self.language_extensions = config.get("language_extensions", {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
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
        })
        
        # Fall back to Python parser for unsupported languages
        self.fallback_to_text = config.get("fallback_to_text", True)
    
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
            language = self._detect_language(file_path)
        
        # If still no language, try to detect from code
        if not language:
            language = self._detect_language_from_code(code)
            self.logger.info(f"Detected language from code: {language}")
        
        # Extract AST based on language
        if language == "python":
            ast_dict = self.python_parser.parse(code)
        elif self.tree_sitter_parser and language in self.tree_sitter_parser.supported_languages():
            ast_dict = self.tree_sitter_parser.parse(code, language)
        else:
            self.logger.warning(f"Unsupported language: {language}")
            if self.fallback_to_text:
                # Fall back to text representation
                ast_dict = self._create_text_representation(code, language)
            else:
                ast_dict = {"error": f"Unsupported language: {language}"}
        
        # Add metadata
        ast_dict["language"] = language
        if file_path:
            ast_dict["file_path"] = file_path
        
        return ast_dict
    
    def extract_ast_from_file(self, file_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract AST from a file.
        
        Args:
            file_path: Path to the source file
            language: Programming language (optional, will be detected if not provided)
            
        Returns:
            Dictionary containing the AST in a standardized format
        """
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            
            # Detect language if not provided
            if not language:
                language = self._detect_language(file_path)
            
            # Extract AST
            return self.extract_ast(code, language, file_path)
            
        except Exception as e:
            self.logger.error(f"Failed to extract AST from file {file_path}: {e}")
            return {
                "error": str(e),
                "file_path": file_path,
                "language": language or "unknown"
            }
    
    def _detect_language(self, file_path: str) -> str:
        """
        Detect programming language from file path.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Detected language or 'unknown'
        """
        ext = os.path.splitext(file_path)[1].lower()
        language = self.language_extensions.get(ext, "unknown")
        return language
    
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
    
    def _create_text_representation(self, code: str, language: str) -> Dict[str, Any]:
        """
        Create a simple text-based AST representation.
        
        Args:
            code: Source code
            language: Programming language
            
        Returns:
            Dictionary with simple text-based AST
        """
        lines = code.splitlines()
        nodes = []
        
        for i, line in enumerate(lines):
            if line.strip():  # Skip empty lines
                nodes.append({
                    "type": "line",
                    "content": line,
                    "line_number": i + 1
                })
        
        return {
            "type": "text",
            "language": language,
            "node_count": len(nodes),
            "nodes": nodes
        }


class PythonParser:
    """Parser for Python using the built-in ast module."""
    
    def parse(self, code: str) -> Dict[str, Any]:
        """
        Parse Python code into AST.
        
        Args:
            code: Python source code
            
        Returns:
            Dictionary containing the AST
        """
        try:
            # Parse the code
            tree = ast.parse(code)
            
            # Convert AST to dictionary
            ast_dict = self._ast_to_dict(tree)
            
            return {
                "type": "ast",
                "language": "python",
                "root": ast_dict,
                "node_count": self._count_nodes(ast_dict)
            }
            
        except SyntaxError as e:
            # Handle syntax errors
            return {
                "type": "error",
                "language": "python",
                "error_type": "SyntaxError",
                "error_message": str(e),
                "error_line": e.lineno,
                "error_col": e.offset
            }
        except Exception as e:
            # Handle other errors
            return {
                "type": "error",
                "language": "python",
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
    
    def _ast_to_dict(self, node) -> Dict[str, Any]:
        """
        Convert a Python AST node to a dictionary.
        
        Args:
            node: AST node
            
        Returns:
            Dictionary representation of the node
        """
        if isinstance(node, ast.AST):
            # Create dictionary for AST node
            result = {
                "type": node.__class__.__name__,
                "attributes": {},
                "children": {}
            }
            
            # Add line and column information if available
            if hasattr(node, "lineno"):
                result["line"] = node.lineno
                if hasattr(node, "col_offset"):
                    result["col"] = node.col_offset
                if hasattr(node, "end_lineno") and node.end_lineno is not None:
                    result["end_line"] = node.end_lineno
                    if hasattr(node, "end_col_offset") and node.end_col_offset is not None:
                        result["end_col"] = node.end_col_offset
            
            # Process special nodes
            if isinstance(node, ast.Name):
                result["attributes"]["name"] = node.id
            elif isinstance(node, ast.Constant):
                result["attributes"]["value"] = repr(node.value)
            elif isinstance(node, ast.FunctionDef):
                result["attributes"]["name"] = node.name
                result["attributes"]["args"] = [arg.arg for arg in node.args.args]
                result["attributes"]["returns"] = self._ast_to_dict(node.returns) if node.returns else None
            elif isinstance(node, ast.ClassDef):
                result["attributes"]["name"] = node.name
                result["attributes"]["bases"] = [self._ast_to_dict(base) for base in node.bases]
            
            # Process children
            for field, value in ast.iter_fields(node):
                if value is None:
                    continue
                elif isinstance(value, list):
                    # Process list of nodes
                    result["children"][field] = [
                        self._ast_to_dict(item) for item in value
                        if isinstance(item, ast.AST)
                    ]
                elif isinstance(value, ast.AST):
                    # Process single node
                    result["children"][field] = self._ast_to_dict(value)
                else:
                    # Process attribute
                    result["attributes"][field] = value
            
            return result
        elif isinstance(node, list):
            return [self._ast_to_dict(item) for item in node]
        else:
            return node
    
    def _count_nodes(self, node: Dict[str, Any]) -> int:
        """
        Count nodes in an AST dictionary.
        
        Args:
            node: Dictionary representation of an AST node
            
        Returns:
            Number of nodes
        """
        if not isinstance(node, dict):
            return 0
        
        count = 1  # Count this node
        
        # Count children
        for field, value in node.get("children", {}).items():
            if isinstance(value, list):
                for item in value:
                    count += self._count_nodes(item)
            else:
                count += self._count_nodes(value)
        
        return count