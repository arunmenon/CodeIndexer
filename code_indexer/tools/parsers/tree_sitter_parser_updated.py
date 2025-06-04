"""
Updated Tree-sitter Parser

Provides a parser implementation using the Tree-sitter library for AST extraction
based on the latest best practices.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Set

# Set up logging
logger = logging.getLogger("updated_tree_sitter_parser")

# Check if tree-sitter is available
try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Dictionary to store language objects
languages = {}

# Initialize languages if tree-sitter is available
if HAS_TREE_SITTER:
    # Try to initialize Python language
    try:
        import tree_sitter_python
        python_language = Language(tree_sitter_python.language())
        languages['python'] = python_language
        logger.info("Loaded tree-sitter-python language")
    except ImportError:
        logger.warning("tree-sitter-python not available. Install with: pip install tree-sitter-python")
    except Exception as e:
        logger.error(f"Error loading Python language: {e}")
    
    # Try to initialize JavaScript language
    try:
        import tree_sitter_javascript
        javascript_language = Language(tree_sitter_javascript.language())
        languages['javascript'] = javascript_language
        logger.info("Loaded tree-sitter-javascript language")
    except ImportError:
        logger.warning("tree-sitter-javascript not available. Install with: pip install tree-sitter-javascript")
    except Exception as e:
        logger.error(f"Error loading JavaScript language: {e}")
    
    # Try to initialize Java language
    try:
        import tree_sitter_java
        java_language = Language(tree_sitter_java.language())
        languages['java'] = java_language
        logger.info("Loaded tree-sitter-java language")
    except ImportError:
        logger.warning("tree-sitter-java not available. Install with: pip install tree-sitter-java")
    except Exception as e:
        logger.error(f"Error loading Java language: {e}")


class UpdatedTreeSitterParser:
    """
    Updated parser implementation using tree-sitter.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Tree-sitter parser.
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(languages.keys())
    
    def parse(self, code: str, language: str) -> Dict[str, Any]:
        """
        Parse code using tree-sitter.
        
        Args:
            code: Source code to parse
            language: Programming language
            
        Returns:
            Dictionary with AST information
        """
        if not HAS_TREE_SITTER:
            return {"error": "Tree-sitter not available"}
        
        if language not in languages:
            return {
                "error": f"Language {language} not supported",
                "supported_languages": list(languages.keys())
            }
        
        try:
            # Create a fresh parser for each parse
            parser = Parser()
            
            # Set the language
            parser.set_language(languages[language])
            
            # Ensure code is bytes
            code_bytes = code.encode('utf8') if isinstance(code, str) else code
            
            # Parse the code
            tree = parser.parse(code_bytes)
            
            # Convert the tree to dictionary
            ast_dict = self._node_to_dict(tree.root_node, code_bytes)
            
            # Add metadata
            ast_dict["language"] = language
            ast_dict["parser"] = "tree-sitter"
            
            return ast_dict
            
        except Exception as e:
            logger.error(f"Error parsing {language} code: {e}")
            return {
                "error": f"Failed to parse {language} code: {str(e)}",
                "language": language
            }
    
    def _node_to_dict(self, node, code_bytes: bytes) -> Dict[str, Any]:
        """
        Convert a tree-sitter node to a dictionary.
        
        Args:
            node: Tree-sitter Node
            code_bytes: Source code as bytes
            
        Returns:
            Dictionary representation of the node
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
            result["children"] = []
            for i in range(node.child_count):
                child_dict = self._node_to_dict(node.children[i], code_bytes)
                result["children"].append(child_dict)
        
        return result