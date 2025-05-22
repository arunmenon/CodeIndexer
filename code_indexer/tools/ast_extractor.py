"""
AST Extractor Tool

Provides a unified interface for extracting Abstract Syntax Trees (ASTs) from
code in different programming languages.
"""

import os
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
        
        # Determine which parser to use
        if config.get("use_tree_sitter", True):
            # Try using our unified tree-sitter implementation first
            try:
                from .parsers.unified_tree_sitter import UnifiedTreeSitterParser, HAS_TREE_SITTER
                if HAS_TREE_SITTER:
                    self.parser = UnifiedTreeSitterParser(config.get("tree_sitter_config", {}))
                    self.logger.info("Using UnifiedTreeSitterParser implementation")
                else:
                    # If tree-sitter not available, try the next option
                    raise ImportError("Tree-sitter not available")
            except (ImportError, Exception) as e:
                self.logger.warning(f"Could not use UnifiedTreeSitterParser: {e}")
                
                # Fall back to other parsers based on environment variable
                env_parser = os.environ.get("TREE_SITTER_PARSER")
                parser_name = config.get("parser_name", "simple_tree_sitter")
                
                if env_parser:
                    parser_name = "simple_tree_sitter" if env_parser == "simple" else "basic_tree_sitter"
                    self.logger.info(f"Using parser specified in environment: {env_parser}")
                
                try:
                    if parser_name == "simple_tree_sitter":
                        from .parsers.simple_tree_sitter import SimpleTreeSitterParser
                        self.parser = SimpleTreeSitterParser(config.get("tree_sitter_config", {}))
                        self.logger.info("Using SimpleTreeSitterParser implementation")
                    else:
                        from .parsers.basic_tree_sitter import BasicTreeSitterParser
                        self.parser = BasicTreeSitterParser(config.get("tree_sitter_config", {}))
                        self.logger.info("Using BasicTreeSitterParser implementation")
                except (ImportError, Exception) as e:
                    self.logger.warning(f"Failed to initialize tree-sitter parser: {e}")
                    # Fall back to native parser
                    from .native_parser import NativeParser
                    self.parser = NativeParser(config.get("parser_config", {}))
                    self.logger.info("Falling back to NativeParser implementation")
        else:
            # Explicitly use native parser
            from .native_parser import NativeParser
            self.parser = NativeParser(config.get("parser_config", {}))
            self.logger.info("Using NativeParser implementation with built-in ast module and regex-based parsers")
        
        # Log supported languages
        supported_langs = self.parser.supported_languages()
        self.logger.info(f"Parser supported languages: {', '.join(supported_langs)}")
        
        # Language detection settings (updated from native parser)
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
        
        # If still no language, try to detect from code
        if not language or language == "unknown":
            language = self._detect_language_from_code(code)
            self.logger.info(f"Detected language from code: {language}")
        
        # Parse the code using our native parser
        ast_dict = self.parser.parse(code, language, file_path)
        
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
            # Detect language if not provided
            if not language:
                language = self.parser.detect_language(file_path)
            
            # Check if parser supports direct file parsing
            if hasattr(self.parser, 'parse_file'):
                return self.parser.parse_file(file_path)
            else:
                # Fallback to reading the file and parsing the content
                self.logger.debug(f"Parser doesn't have parse_file method, reading file contents")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    return self.parser.parse(code, language, file_path)
                except UnicodeDecodeError:
                    # Try with a different encoding for binary files
                    self.logger.warning(f"Unicode decode error for {file_path}, skipping")
                    return {
                        "error": f"Unable to decode file as text: {file_path}",
                        "file_path": file_path
                    }
            
        except Exception as e:
            self.logger.error(f"Failed to extract AST from file {file_path}: {e}")
            return {
                "error": str(e),
                "file_path": file_path,
                "language": language or "unknown"
            }
    
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