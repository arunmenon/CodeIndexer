"""
Direct Tree-sitter Parser

This is a simpler implementation that directly uses the tree-sitter library.
It creates a separate parser for each language and doesn't try to be fancy.
"""

import os
import logging
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("direct_tree_sitter_parser")

# Check if tree-sitter is available
try:
    from tree_sitter import Parser
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Language-specific parsers
python_parser = None
javascript_parser = None
java_parser = None

# Try to create a Python parser
if HAS_TREE_SITTER:
    try:
        import tree_sitter_python
        python_parser = Parser()
        python_parser.language = tree_sitter_python.language()
        logger.info("Created Python parser")
    except ImportError:
        logger.warning("tree-sitter-python not available. Install with: pip install tree-sitter-python")
    except Exception as e:
        logger.error(f"Error creating Python parser: {e}")

# Try to create a JavaScript parser
if HAS_TREE_SITTER:
    try:
        import tree_sitter_javascript
        javascript_parser = Parser()
        javascript_parser.language = tree_sitter_javascript.language()
        logger.info("Created JavaScript parser")
    except ImportError:
        logger.warning("tree-sitter-javascript not available. Install with: pip install tree-sitter-javascript")
    except Exception as e:
        logger.error(f"Error creating JavaScript parser: {e}")

# Try to create a Java parser
if HAS_TREE_SITTER:
    try:
        import tree_sitter_java
        java_parser = Parser()
        java_parser.language = tree_sitter_java.language()
        logger.info("Created Java parser")
    except ImportError:
        logger.warning("tree-sitter-java not available. Install with: pip install tree-sitter-java")
    except Exception as e:
        logger.error(f"Error creating Java parser: {e}")


class DirectTreeSitterParser:
    """
    A direct implementation of Tree-sitter parser without fancy abstractions.
    
    This implementation creates a separate parser for each supported language.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Tree-sitter parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        languages = set()
        if python_parser is not None:
            languages.add("python")
        if javascript_parser is not None:
            languages.add("javascript")
        if java_parser is not None:
            languages.add("java")
        return languages
    
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
        
        # Get the appropriate parser for the language
        parser = None
        if language == "python" and python_parser is not None:
            parser = python_parser
        elif language == "javascript" and javascript_parser is not None:
            parser = javascript_parser
        elif language == "java" and java_parser is not None:
            parser = java_parser
        
        # Check if the language is supported
        if parser is None:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(self.supported_languages()),
                "language": language
            }
        
        try:
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