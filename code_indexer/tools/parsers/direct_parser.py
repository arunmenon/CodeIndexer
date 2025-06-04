"""
Direct Tree-sitter Parser

This implementation uses the tree-sitter API with language modules installed 
directly through pip (tree-sitter-python, tree-sitter-javascript, etc.).
"""

import os
import sys
import logging
from importlib import import_module
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("direct_parser")

# Check if tree-sitter is available
try:
    from tree_sitter import Parser
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Global variables
LANGUAGE_MODULES = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "java": "tree_sitter_java"
}

# Initialize parsers
PARSERS = {}

def setup_parsers():
    """Set up tree-sitter parsers for each language."""
    global PARSERS
    
    if not HAS_TREE_SITTER:
        logger.error("Tree-sitter not available, cannot set up parsers")
        return False
    
    try:
        for lang, module_name in LANGUAGE_MODULES.items():
            # Check if the module is installed
            try:
                # Try to import the module
                module = import_module(module_name)
                
                # Check if the module has a language() function
                if hasattr(module, 'language'):
                    # Create a parser and use the language
                    parser = Parser()
                    
                    # Try to directly set the language
                    try:
                        lang_obj = module.language()
                        parser.language = lang_obj
                        PARSERS[lang] = parser
                        logger.info(f"Successfully created parser for {lang}")
                    except Exception as e:
                        logger.error(f"Failed to set language for {lang}: {e}")
                else:
                    logger.error(f"Module {module_name} does not have a language() function")
            except ImportError:
                logger.warning(f"Module {module_name} not installed. Install with: pip install {module_name}")
            except Exception as e:
                logger.error(f"Error setting up parser for {lang}: {e}")
        
        return len(PARSERS) > 0
        
    except Exception as e:
        logger.error(f"Error setting up tree-sitter parsers: {e}")
        return False

# Set up parsers on module import
if HAS_TREE_SITTER:
    setup_parsers()


class DirectParser:
    """
    Direct tree-sitter parser implementation using pre-installed language modules.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(PARSERS.keys())
    
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
        if language not in PARSERS:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(PARSERS.keys()),
                "language": language
            }
        
        try:
            # Get the parser for this language
            parser = PARSERS[language]
            
            # Ensure code is bytes
            code_bytes = code.encode('utf8') if isinstance(code, str) else code
            
            # Parse the code
            tree = parser.parse(code_bytes)
            
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
        # Skip null nodes
        if node is None:
            return {"type": "null"}
        
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