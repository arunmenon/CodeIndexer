"""
Direct Tree-Sitter Parser

This implementation directly uses the tree-sitter API with a workaround
to handle capsule objects from language modules.
"""

import os
import sys
import logging
import importlib
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("direct_ts_parser")

# Check if tree-sitter is available
try:
    import tree_sitter
    from tree_sitter import Parser
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Create standalone parse functions for each language
def create_python_parser():
    """Create a parser for Python."""
    if not HAS_TREE_SITTER:
        return None
    
    try:
        import tree_sitter_python
        parser = Parser()
        
        # Get the language capsule
        if hasattr(tree_sitter_python, 'language'):
            lang_capsule = tree_sitter_python.language()
            
            # Initialize parser
            parser.set_language = lambda: None  # Dummy method to avoid errors
            
            # Use low-level approach to parse
            def parse_python(code):
                try:
                    code_bytes = code.encode('utf8') if isinstance(code, str) else code
                    tree = parser.parse(code_bytes)
                    return tree
                except Exception as e:
                    logger.error(f"Error parsing Python code: {e}")
                    return None
            
            parser.parse = parse_python
            logger.info("Python parser ready")
            return parser
        else:
            logger.error("tree_sitter_python has no language() function")
            return None
    except ImportError:
        logger.warning("tree-sitter-python not available")
        return None
    except Exception as e:
        logger.error(f"Error creating Python parser: {e}")
        return None

def create_javascript_parser():
    """Create a parser for JavaScript."""
    if not HAS_TREE_SITTER:
        return None
    
    try:
        import tree_sitter_javascript
        parser = Parser()
        
        # Get the language capsule
        if hasattr(tree_sitter_javascript, 'language'):
            lang_capsule = tree_sitter_javascript.language()
            
            # Initialize parser
            parser.set_language = lambda: None  # Dummy method to avoid errors
            
            # Use low-level approach to parse
            def parse_javascript(code):
                try:
                    code_bytes = code.encode('utf8') if isinstance(code, str) else code
                    tree = parser.parse(code_bytes)
                    return tree
                except Exception as e:
                    logger.error(f"Error parsing JavaScript code: {e}")
                    return None
            
            parser.parse = parse_javascript
            logger.info("JavaScript parser ready")
            return parser
        else:
            logger.error("tree_sitter_javascript has no language() function")
            return None
    except ImportError:
        logger.warning("tree-sitter-javascript not available")
        return None
    except Exception as e:
        logger.error(f"Error creating JavaScript parser: {e}")
        return None

def create_java_parser():
    """Create a parser for Java."""
    if not HAS_TREE_SITTER:
        return None
    
    try:
        import tree_sitter_java
        parser = Parser()
        
        # Get the language capsule
        if hasattr(tree_sitter_java, 'language'):
            lang_capsule = tree_sitter_java.language()
            
            # Initialize parser
            parser.set_language = lambda: None  # Dummy method to avoid errors
            
            # Use low-level approach to parse
            def parse_java(code):
                try:
                    code_bytes = code.encode('utf8') if isinstance(code, str) else code
                    tree = parser.parse(code_bytes)
                    return tree
                except Exception as e:
                    logger.error(f"Error parsing Java code: {e}")
                    return None
            
            parser.parse = parse_java
            logger.info("Java parser ready")
            return parser
        else:
            logger.error("tree_sitter_java has no language() function")
            return None
    except ImportError:
        logger.warning("tree-sitter-java not available")
        return None
    except Exception as e:
        logger.error(f"Error creating Java parser: {e}")
        return None

# Initialize parsers
PYTHON_PARSER = create_python_parser()
JAVASCRIPT_PARSER = create_javascript_parser()
JAVA_PARSER = create_java_parser()

class DirectTSParser:
    """
    Direct Tree-sitter parser implementation using multiple parsers.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Create new parsers if needed
        self.parsers = {}
        if PYTHON_PARSER is not None:
            self.parsers["python"] = PYTHON_PARSER
        if JAVASCRIPT_PARSER is not None:
            self.parsers["javascript"] = JAVASCRIPT_PARSER
        if JAVA_PARSER is not None:
            self.parsers["java"] = JAVA_PARSER
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(self.parsers.keys())
    
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
        if language not in self.parsers:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(self.parsers.keys()),
                "language": language
            }
        
        try:
            # Get the parser for this language
            parser = self.parsers[language]
            
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