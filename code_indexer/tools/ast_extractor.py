"""
AST Extractor Tool

This module provides a unified interface for extracting abstract syntax trees (ASTs)
from code in different languages using native Python ast module for Python
and Tree-Sitter for other languages.
"""

import ast
import json
import logging
import os
import pathlib
from typing import Dict, List, Optional, Union, Any

# Import tree-sitter conditionally to handle environments without it
try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    logging.warning("Tree-sitter not installed. Only Python parsing will be available.")

from google.adk import Tool
from code_indexer.utils.ast_utils import ast_to_dict


class ASTExtractorTool(Tool):
    """
    Unified AST extraction for multiple languages.
    
    Provides a consistent interface to extract ASTs from code files in different
    languages, returning a standardized JSON-serializable tree structure.
    
    Currently supported languages:
    - Python (using native ast module)
    - Java (using Tree-Sitter)
    - JavaScript (using Tree-Sitter)
    """

    def __init__(self):
        """Initialize the AST extractor tool."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.ts_parsers = {}  # Cache of Tree-Sitter parsers
        
        # Grammar paths configuration
        self.grammar_paths = {
            "java": os.environ.get("TS_JAVA_GRAMMAR_PATH", "vendor/tree-sitter-java"),
            "javascript": os.environ.get("TS_JS_GRAMMAR_PATH", "vendor/tree-sitter-javascript"),
            # Add other supported languages here
        }
        
        # Check if tree-sitter is available for non-Python languages
        if not HAS_TREE_SITTER:
            self.logger.warning(
                "Tree-Sitter not available. Only Python parsing will work. "
                "Install tree-sitter for multi-language support."
            )
    
    def _ts_parser(self, lang: str) -> Optional[Parser]:
        """
        Get or create a Tree-Sitter parser for the specified language.
        
        Args:
            lang: Language identifier (e.g., "java", "javascript")
            
        Returns:
            A configured Tree-Sitter parser or None if unavailable
        """
        if not HAS_TREE_SITTER:
            return None
            
        # Return cached parser if available
        if lang in self.ts_parsers:
            return self.ts_parsers[lang]
        
        # Check if language grammar path is configured
        if lang not in self.grammar_paths:
            self.logger.error(f"Language {lang} not supported. No grammar path configured.")
            return None
        
        try:
            # Build language library
            grammar_path = self.grammar_paths[lang]
            so_path = f"/tmp/tree-sitter-{lang}.so"
            
            Language.build_library(so_path, [grammar_path])
            
            # Create and configure parser
            parser = Parser()
            parser.set_language(Language(so_path, lang))
            
            # Cache parser for future use
            self.ts_parsers[lang] = parser
            return parser
        except Exception as e:
            self.logger.error(f"Error creating Tree-Sitter parser for {lang}: {e}")
            return None
    
    def extract(self, path: str, lang: str) -> Dict[str, Any]:
        """
        Extract AST from a source file.
        
        Args:
            path: Path to the source file
            lang: Language identifier (e.g., "python", "java")
            
        Returns:
            A dictionary representing the AST of the source file
        
        Raises:
            ValueError: If the file doesn't exist or can't be parsed
        """
        if not os.path.exists(path):
            raise ValueError(f"File not found: {path}")
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                code = file.read()
                
            # Handle Python using native ast module
            if lang.lower() == "python":
                py_ast = ast.parse(code)
                return ast_to_dict(py_ast, code)
            
            # Handle other languages with Tree-Sitter
            parser = self._ts_parser(lang.lower())
            if not parser:
                raise ValueError(f"No parser available for language: {lang}")
            
            # Parse code with Tree-Sitter
            tree = parser.parse(bytes(code, "utf8"))
            
            # Convert Tree-Sitter AST to our standard format
            return self._ts_tree_to_dict(tree.root_node, code)
        
        except Exception as e:
            self.logger.error(f"Error extracting AST from {path}: {e}")
            raise ValueError(f"Failed to parse {path}: {str(e)}")
    
    def _ts_tree_to_dict(self, node, source_code: str) -> Dict[str, Any]:
        """
        Convert a Tree-Sitter AST to a standardized dictionary format.
        
        Args:
            node: Tree-Sitter AST node
            source_code: Original source code text
            
        Returns:
            Dictionary representation of the AST
        """
        # Extract node text
        start_byte = node.start_byte
        end_byte = node.end_byte
        text = source_code[start_byte:end_byte]
        
        # Build node representation
        result = {
            "type": node.type,
            "text": text,
            "start_position": {
                "row": node.start_point[0],
                "column": node.start_point[1]
            },
            "end_position": {
                "row": node.end_point[0],
                "column": node.end_point[1]
            }
        }
        
        # Add children if any
        if node.child_count > 0:
            result["children"] = [
                self._ts_tree_to_dict(child, source_code)
                for child in node.children
            ]
        
        return result
    
    def find_calls(self, ast_dict: Dict[str, Any], lang: str) -> List[str]:
        """
        Extract function/method calls from an AST.
        
        Args:
            ast_dict: AST dictionary returned by extract()
            lang: Language identifier (e.g., "python", "java")
            
        Returns:
            List of fully-qualified names being called in the code
        """
        calls = []
        
        if lang.lower() == "python":
            calls = self._find_python_calls(ast_dict)
        else:
            calls = self._find_ts_calls(ast_dict, lang.lower())
            
        return calls
    
    def _find_python_calls(self, ast_dict: Dict[str, Any]) -> List[str]:
        """Find calls in Python AST."""
        calls = []
        
        # Process node based on type
        if ast_dict["type"] == "Call":
            # Extract function name for direct calls
            if "children" in ast_dict:
                for child in ast_dict["children"]:
                    if child["type"] == "Name" or child["type"] == "Attribute":
                        calls.append(child["text"])
        
        # Recursively process children
        if "children" in ast_dict:
            for child in ast_dict["children"]:
                calls.extend(self._find_python_calls(child))
        
        return calls
    
    def _find_ts_calls(self, ast_dict: Dict[str, Any], lang: str) -> List[str]:
        """Find calls in Tree-Sitter AST."""
        calls = []
        
        # Handle Java calls
        if lang == "java":
            if ast_dict["type"] == "method_invocation":
                # Extract method name
                if "children" in ast_dict:
                    for child in ast_dict["children"]:
                        if child["type"] == "identifier":
                            calls.append(child["text"])
        
        # Handle JavaScript calls
        elif lang == "javascript":
            if ast_dict["type"] == "call_expression":
                # Extract function name
                if "children" in ast_dict:
                    for child in ast_dict["children"]:
                        if child["type"] == "identifier" or child["type"] == "member_expression":
                            calls.append(child["text"])
        
        # Recursively process children
        if "children" in ast_dict:
            for child in ast_dict["children"]:
                calls.extend(self._find_ts_calls(child, lang))
        
        return calls