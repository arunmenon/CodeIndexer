"""
Adapted Tree-sitter Parser

This implementation adapts to the current tree-sitter API and works
with the pre-compiled language modules available through pip.
"""

import os
import sys
import logging
import ctypes
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("adapted_tree_sitter_parser")

# Check if tree-sitter is available
try:
    import tree_sitter
    from tree_sitter import Parser
    HAS_TREE_SITTER = True
    logger.info(f"Tree-sitter package is available: version {getattr(tree_sitter, '__version__', 'unknown')}")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")


class AdaptedTreeSitterParser:
    """
    Parser implementation that adapts to the current tree-sitter API.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Tree-sitter parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.parser = Parser() if HAS_TREE_SITTER else None
        
        # Direct use of the language modules
        self.languages = {}
        self._load_languages()
    
    def _load_languages(self):
        """Load language modules directly."""
        if not HAS_TREE_SITTER:
            return
        
        # Try to load Python
        try:
            import tree_sitter_python
            self.languages["python"] = tree_sitter_python.language()
            logger.info("Loaded Python language module")
        except ImportError:
            logger.warning("tree-sitter-python not available. Install with: pip install tree-sitter-python")
        except Exception as e:
            logger.error(f"Error loading Python language: {e}")
        
        # Try to load JavaScript
        try:
            import tree_sitter_javascript
            self.languages["javascript"] = tree_sitter_javascript.language()
            logger.info("Loaded JavaScript language module")
        except ImportError:
            logger.warning("tree-sitter-javascript not available. Install with: pip install tree-sitter-javascript")
        except Exception as e:
            logger.error(f"Error loading JavaScript language: {e}")
        
        # Try to load Java
        try:
            import tree_sitter_java
            self.languages["java"] = tree_sitter_java.language()
            logger.info("Loaded Java language module")
        except ImportError:
            logger.warning("tree-sitter-java not available. Install with: pip install tree-sitter-java")
        except Exception as e:
            logger.error(f"Error loading Java language: {e}")
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(self.languages.keys())
    
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
        if language not in self.languages:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(self.languages.keys()),
                "language": language
            }
        
        try:
            # Reset the parser to ensure clean state
            self.parser.reset()
            
            # Try to set the language using the language property
            # We catch any TypeError since the language object might be a PyCapsule
            try:
                self.parser.language = self.languages[language]
            except TypeError as e:
                logger.warning(f"Could not set language using property: {e}")
                # Use the C binding directly if possible
                if hasattr(tree_sitter.binding, '_C') and hasattr(tree_sitter.binding._C, 'ts_parser_set_language'):
                    tree_sitter.binding._C.ts_parser_set_language(self.parser._parser, self.languages[language])
                else:
                    raise TypeError("Cannot set parser language: incompatible API")
            
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