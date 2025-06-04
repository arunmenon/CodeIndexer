"""
Simple Tree-sitter Parser

Uses the tree-sitter bindings available through the pip-installable packages.
This implementation is compatible with the newer tree-sitter Python API.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Set

# Set up logging
logger = logging.getLogger("simple_tree_sitter_parser")

# Check if tree-sitter is available
try:
    import tree_sitter
    from tree_sitter import Parser
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Dictionary to store language objects and parsers
LANGUAGES = {}
PARSERS = {}

# Initialize languages if tree-sitter is available
if HAS_TREE_SITTER:
    # Initialize Python language
    try:
        import tree_sitter_python
        # Get the Language object - different packages provide this differently
        try:
            # First try the language method if available
            language_obj = tree_sitter_python.language()
            LANGUAGES['python'] = language_obj
        except (AttributeError, TypeError):
            # If not, try the direct language object or function 
            if hasattr(tree_sitter_python, 'language'):
                LANGUAGES['python'] = tree_sitter_python.language
            elif hasattr(tree_sitter_python, 'Language'):
                LANGUAGES['python'] = tree_sitter_python.Language
        
        # Create parser for this language
        python_parser = Parser()
        python_parser.set_language(LANGUAGES['python'])
        PARSERS['python'] = python_parser
        
        logger.info("Initialized Python language")
    except (ImportError, Exception) as e:
        logger.warning(f"tree-sitter-python issue: {e}")
    
    # Initialize JavaScript language
    try:
        import tree_sitter_javascript
        # Get the Language object
        try:
            # First try the language method if available
            language_obj = tree_sitter_javascript.language()
            LANGUAGES['javascript'] = language_obj
        except (AttributeError, TypeError):
            # If not, try the direct language object or function
            if hasattr(tree_sitter_javascript, 'language'):
                LANGUAGES['javascript'] = tree_sitter_javascript.language
            elif hasattr(tree_sitter_javascript, 'Language'):
                LANGUAGES['javascript'] = tree_sitter_javascript.Language
        
        # Create parser for this language
        js_parser = Parser()
        js_parser.set_language(LANGUAGES['javascript'])
        PARSERS['javascript'] = js_parser
        
        logger.info("Initialized JavaScript language")
    except (ImportError, Exception) as e:
        logger.warning(f"tree-sitter-javascript issue: {e}")
    
    # Initialize Java language
    try:
        import tree_sitter_java
        # Get the Language object
        try:
            # First try the language method if available
            language_obj = tree_sitter_java.language()
            LANGUAGES['java'] = language_obj
        except (AttributeError, TypeError):
            # If not, try the direct language object or function
            if hasattr(tree_sitter_java, 'language'):
                LANGUAGES['java'] = tree_sitter_java.language
            elif hasattr(tree_sitter_java, 'Language'):
                LANGUAGES['java'] = tree_sitter_java.Language
        
        # Create parser for this language
        java_parser = Parser()
        java_parser.set_language(LANGUAGES['java'])
        PARSERS['java'] = java_parser
        
        logger.info("Initialized Java language")
    except (ImportError, Exception) as e:
        logger.warning(f"tree-sitter-java issue: {e}")


class SimpleTreeSitterParser:
    """
    Simple parser implementation using pre-configured tree-sitter parsers.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the parser.
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}
        self.parsers = PARSERS
        
        # Log languages we've loaded
        if self.parsers:
            logger.info(f"Available languages: {', '.join(self.parsers.keys())}")
        else:
            logger.warning("No parsers available. Install tree-sitter language packages.")
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(self.parsers.keys())
        
    def detect_language(self, file_path: str) -> str:
        """
        Detect the programming language from a file path.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Language name or "unknown"
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # Map extensions to languages
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
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
        }
        
        return extension_map.get(ext, "unknown")
    
    def parse_code(self, code: str, language: str) -> Dict[str, Any]:
        """
        Parse code using tree-sitter.
        
        Args:
            code: Source code to parse
            language: Programming language
            
        Returns:
            Parsed AST in dictionary format
        """
        parser = self.parsers.get(language)
        
        if not parser:
            return {
                "error": f"No parser available for {language}",
                "type": "error",
                "language": language
            }
        
        try:
            # Parse code with tree-sitter
            tree = parser.parse(bytes(code, "utf8"))
            
            # Convert to dictionary format
            ast_dict = self._convert_tree_to_dict(tree.root_node)
            
            # Add metadata
            ast_dict["language"] = language
            ast_dict["parser"] = "tree-sitter"
            ast_dict["_ast_format"] = "tree-sitter"
            
            return ast_dict
            
        except Exception as e:
            logger.error(f"Error parsing {language} code: {e}")
            return {
                "error": str(e),
                "type": "error",
                "language": language
            }
    
    def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """
        Convert a tree-sitter node to a dictionary.
        
        Args:
            node: Tree-sitter node
            
        Returns:
            Dictionary representation
        """
        if not node:
            return {}
        
        result = {
            "type": node.type,
            "start_point": [node.start_point[0], node.start_point[1]],
            "end_point": [node.end_point[0], node.end_point[1]]
        }
        
        # Add is_named property
        if hasattr(node, 'is_named'):
            result["is_named"] = node.is_named
        
        # Add text for leaf nodes
        if not node.children:
            try:
                result["text"] = node.text.decode('utf-8', errors='replace')
            except (AttributeError, UnicodeDecodeError):
                result["text"] = str(node.text) if hasattr(node, 'text') else ""
        
        # Process children recursively
        if node.children:
            result["children"] = [self._convert_tree_to_dict(child) for child in node.children]
        
        return result