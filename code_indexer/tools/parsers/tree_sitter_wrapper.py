"""
Tree-sitter Wrapper

This module provides a simpler approach to using tree-sitter with pre-compiled language modules.
"""

import logging
from typing import Dict, Any

# Set up logging
logger = logging.getLogger("tree_sitter_wrapper")

# Check if tree-sitter is available
try:
    import tree_sitter
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Dictionary to track available language modules
LANGUAGE_MODULES = {}

# Initialize language modules
if HAS_TREE_SITTER:
    try:
        import tree_sitter_python
        LANGUAGE_MODULES['python'] = tree_sitter_python
        logger.info("tree-sitter-python is available")
    except ImportError:
        logger.warning("tree-sitter-python not available. Install with: pip install tree-sitter-python")
    
    try:
        import tree_sitter_javascript
        LANGUAGE_MODULES['javascript'] = tree_sitter_javascript
        logger.info("tree-sitter-javascript is available")
    except ImportError:
        logger.warning("tree-sitter-javascript not available. Install with: pip install tree-sitter-javascript")
    
    try:
        import tree_sitter_java
        LANGUAGE_MODULES['java'] = tree_sitter_java
        logger.info("tree-sitter-java is available")
    except ImportError:
        logger.warning("tree-sitter-java not available. Install with: pip install tree-sitter-java")

def parse_code(code: str, language: str) -> Dict[str, Any]:
    """
    Parse code using tree-sitter.
    
    Args:
        code: Source code to parse
        language: Programming language
        
    Returns:
        Dictionary with parsing result or error
    """
    if not HAS_TREE_SITTER:
        return {"error": "Tree-sitter not available"}
    
    if language not in LANGUAGE_MODULES:
        return {
            "error": f"Language {language} not supported",
            "supported_languages": list(LANGUAGE_MODULES.keys())
        }
    
    try:
        # Get the language module
        lang_module = LANGUAGE_MODULES[language]
        
        # Create a fresh parser
        parser = tree_sitter.Parser()
        
        # Set the language
        try:
            parser.language = lang_module.language()
        except Exception as e:
            return {
                "error": f"Failed to set language for {language}: {str(e)}"
            }
        
        # Ensure code is bytes
        code_bytes = code.encode('utf8') if isinstance(code, str) else code
        
        # Parse the code
        tree = parser.parse(code_bytes)
        
        # Convert the tree to a dictionary
        result = {
            "type": "module",
            "language": language,
            "parser": "tree-sitter",
            "root": _node_to_dict(tree.root_node, code_bytes)
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error parsing {language} code: {e}")
        return {
            "error": f"Failed to parse {language} code: {str(e)}",
            "language": language
        }

def _node_to_dict(node, code_bytes: bytes) -> Dict[str, Any]:
    """
    Convert a tree-sitter node to a dictionary.
    
    Args:
        node: Tree-sitter Node
        code_bytes: Original source code as bytes
        
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
            child_dict = _node_to_dict(node.children[i], code_bytes)
            result["children"].append(child_dict)
    
    return result

def get_supported_languages():
    """Get a list of supported languages."""
    return list(LANGUAGE_MODULES.keys())