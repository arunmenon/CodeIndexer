"""
Proper Tree-sitter Parser

Uses the tree-sitter library with languages properly built from source.
This follows the recommended approach in the tree-sitter documentation.
"""

import os
import logging
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("proper_tree_sitter_parser")

# Import the setup function
from ..setup_tree_sitter import setup_tree_sitter_languages

# Check if tree-sitter is available
try:
    from tree_sitter import Parser, Language
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Initialize language objects
languages = {}
languages_lib_path = None

# Set up tree-sitter languages
if HAS_TREE_SITTER:
    success, lib_path, message = setup_tree_sitter_languages()
    if success:
        languages_lib_path = lib_path
        logger.info(f"Using tree-sitter languages library at: {lib_path}")
        
        # Load languages from the library
        try:
            languages["python"] = Language(lib_path, "python")
            logger.info("Loaded Python language")
        except Exception as e:
            logger.error(f"Error loading Python language: {e}")
        
        try:
            languages["javascript"] = Language(lib_path, "javascript")
            logger.info("Loaded JavaScript language")
        except Exception as e:
            logger.error(f"Error loading JavaScript language: {e}")
        
        try:
            languages["java"] = Language(lib_path, "java")
            logger.info("Loaded Java language")
        except Exception as e:
            logger.error(f"Error loading Java language: {e}")
    else:
        logger.error(f"Failed to set up tree-sitter languages: {message}")

# Expose these variables to importers
__all__ = ['ProperTreeSitterParser', 'HAS_TREE_SITTER']


class ProperTreeSitterParser:
    """
    Parser implementation using properly built tree-sitter languages.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Tree-sitter parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.parser = Parser() if HAS_TREE_SITTER else None
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(languages.keys())
    
    def parse(self, code: str, language: str) -> Dict[str, Any]:
        """
        Parse code using Tree-sitter.
        
        Args:
            code: Source code to parse
            language: Programming language
            
        Returns:
            Dictionary with AST information
        """
        # Check if tree-sitter is available
        if not HAS_TREE_SITTER:
            return {"error": "Tree-sitter not available"}
        
        # Check if language is supported
        if language not in languages:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(languages.keys()),
                "language": language
            }
        
        try:
            # Set the parser's language
            self.parser.language = languages[language]
            
            # Ensure code is bytes
            code_bytes = code.encode('utf8') if isinstance(code, str) else code
            
            # Parse the code
            tree = self.parser.parse(code_bytes)
            
            if tree is None:
                raise ValueError("Parsing returned None")
            
            # Convert the tree to our format
            ast_dict = self._visit_tree(tree.root_node, code_bytes)
            
            # Add metadata
            ast_dict["language"] = language
            ast_dict["parser"] = "tree-sitter"
            
            return ast_dict
            
        except Exception as e:
            logger.error(f"Error parsing {language} code: {e}")
            return {
                "error": f"Failed to parse {language} code using tree-sitter: {str(e)}",
                "language": language
            }
    
    def _visit_tree(self, node, code_bytes: bytes) -> Dict[str, Any]:
        """
        Visit a tree-sitter Node and convert it to our AST format.
        
        Args:
            node: Tree-sitter Node
            code_bytes: Original source code as bytes
            
        Returns:
            Dictionary representation of the AST
        """
        result = {
            "type": node.type,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
            "start_point": {"row": node.start_point[0], "column": node.start_point[1]},
            "end_point": {"row": node.end_point[0], "column": node.end_point[1]},
        }
        
        # Add text content for leaf nodes
        if node.child_count == 0:
            try:
                result["text"] = code_bytes[node.start_byte:node.end_byte].decode('utf8')
            except Exception:
                result["text"] = "<binary data>"
        
        # Process children
        if node.child_count > 0:
            result["children"] = [self._visit_tree(node.children[i], code_bytes) for i in range(node.child_count)]
        
        return result