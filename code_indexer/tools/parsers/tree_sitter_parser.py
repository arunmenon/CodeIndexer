"""
Tree-sitter Parser

Provides a parser implementation using the Tree-sitter library for AST extraction.
"""

import os
import logging
import tempfile
from typing import Dict, Any, List, Optional, Set

try:
    import tree_sitter
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

logger = logging.getLogger("tree_sitter_parser")


class TreeSitterParser:
    """
    Parser implementation using Tree-sitter for AST extraction.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Tree-sitter parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self._parsers = {}
        self._languages = {}
        
        # Setup Tree-sitter if available
        if not HAS_TREE_SITTER:
            logger.warning("Tree-sitter not available. Please install with: pip install tree-sitter")
            return
            
        # Setup Tree-sitter language libraries
        self._setup_languages()
    
    def _setup_languages(self) -> None:
        """Set up Tree-sitter language libraries."""
        if not HAS_TREE_SITTER:
            return
            
        # Define language configurations
        language_configs = {
            "python": {"repo": "tree-sitter-python", "lib_name": "python"},
            "javascript": {"repo": "tree-sitter-javascript", "lib_name": "javascript"},
            "typescript": {"repo": "tree-sitter-typescript", "lib_name": "typescript"},
            "java": {"repo": "tree-sitter-java", "lib_name": "java"},
            "c": {"repo": "tree-sitter-c", "lib_name": "c"},
            "cpp": {"repo": "tree-sitter-cpp", "lib_name": "cpp"},
            "go": {"repo": "tree-sitter-go", "lib_name": "go"},
            "ruby": {"repo": "tree-sitter-ruby", "lib_name": "ruby"},
            "rust": {"repo": "tree-sitter-rust", "lib_name": "rust"},
            "bash": {"repo": "tree-sitter-bash", "lib_name": "bash"}
        }
        
        # Get language libraries directory
        lib_dir = self.config.get("lib_dir")
        if not lib_dir:
            # Check common locations
            for path in [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "tree-sitter-libs"),
                os.path.expanduser("~/.tree-sitter-libs"),
            ]:
                if os.path.exists(path):
                    lib_dir = path
                    break
                    
            # Create directory if not found
            if not lib_dir:
                lib_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tree-sitter-libs")
                os.makedirs(lib_dir, exist_ok=True)
        
        # Try to load language libraries without building (for speed)
        for lang_name, lang_config in language_configs.items():
            try:
                lib_path = os.path.join(lib_dir, f"{lang_name}.so")
                if os.path.exists(lib_path):
                    language = Language(lib_path, lang_name)
                    self._languages[lang_name] = language
                    
                    parser = Parser()
                    parser.set_language(language)
                    self._parsers[lang_name] = parser
                    logger.info(f"Loaded {lang_name} parser from {lib_path}")
            except Exception as e:
                logger.warning(f"Failed to load {lang_name} parser: {e}")
        
        # Log the loaded languages
        if self._languages:
            logger.info(f"Loaded Tree-sitter languages: {', '.join(self._languages.keys())}")
        else:
            logger.warning("No Tree-sitter language libraries found. Parser will use fallback methods.")
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(self._parsers.keys())
    
    def parse(self, code: str, language: str) -> Dict[str, Any]:
        """
        Parse code using Tree-sitter.
        
        Args:
            code: Source code to parse
            language: Programming language
            
        Returns:
            Dictionary with AST information
        """
        if not HAS_TREE_SITTER:
            return {"error": "Tree-sitter not available"}
            
        if language not in self._parsers:
            return {"error": f"Unsupported language: {language}"}
        
        try:
            # Parse the code
            parser = self._parsers[language]
            tree = parser.parse(bytes(code, "utf8"))
            
            # Convert to dictionary
            ast_dict = self._convert_tree_to_dict(tree.root_node)
            
            # Add metadata
            ast_dict["language"] = language
            ast_dict["parser"] = "tree-sitter"
            
            return ast_dict
        except Exception as e:
            logger.error(f"Error parsing {language} code: {e}")
            return {"error": str(e)}
    
    def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """
        Convert a Tree-sitter node to a dictionary.
        
        Args:
            node: Tree-sitter node
            
        Returns:
            Dictionary representation of the node
        """
        if not node:
            return {}
        
        result = {
            "type": node.type,
            "start_position": {
                "row": node.start_point[0],
                "column": node.start_point[1],
                "byte": node.start_byte
            },
            "end_position": {
                "row": node.end_point[0],
                "column": node.end_point[1],
                "byte": node.end_byte
            }
        }
        
        # Add field information for named nodes
        if node.is_named:
            result["is_named"] = True
            
            # Include the node text for leaf nodes (no children)
            if len(node.children) == 0:
                result["text"] = node.text.decode('utf-8', errors='replace')
            
            # Convert children
            if node.children:
                result["children"] = [
                    self._convert_tree_to_dict(child)
                    for child in node.children
                ]
        
        return result