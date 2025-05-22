"""
Tree-sitter Parser Implementation

Uses the tree-sitter library by building language parsers from source
following the official approach from the tree-sitter documentation.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("ts_parser")

# Check if tree-sitter is available
try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Global variables
REPO_URLS = {
    "python": "https://github.com/tree-sitter/tree-sitter-python",
    "javascript": "https://github.com/tree-sitter/tree-sitter-javascript",
    "java": "https://github.com/tree-sitter/tree-sitter-java"
}

# Initialize parser and languages
PARSER = None
LANGUAGES = {}
LANGUAGES_LIB_PATH = None

def setup_languages():
    """Set up tree-sitter languages by cloning and building from source."""
    global PARSER, LANGUAGES, LANGUAGES_LIB_PATH
    
    if not HAS_TREE_SITTER:
        logger.error("Tree-sitter not available, cannot set up languages")
        return False
    
    try:
        # Create directory for language repositories
        build_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tree-sitter-libs")
        os.makedirs(build_dir, exist_ok=True)
        
        # Set languages library path
        LANGUAGES_LIB_PATH = os.path.join(build_dir, "languages.so")
        
        # Clone repositories if needed
        repo_paths = {}
        for lang, repo_url in REPO_URLS.items():
            repo_path = os.path.join(build_dir, f"tree-sitter-{lang}")
            
            if not os.path.exists(repo_path):
                logger.info(f"Cloning {lang} repository...")
                try:
                    subprocess.run(["git", "clone", repo_url, repo_path], check=True)
                    logger.info(f"Successfully cloned {lang} repository")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to clone {lang} repository: {e}")
                    continue
            else:
                logger.info(f"Using existing {lang} repository at {repo_path}")
            
            repo_paths[lang] = repo_path
        
        # Build languages library if needed
        if not os.path.exists(LANGUAGES_LIB_PATH) or len(repo_paths) > len(LANGUAGES):
            logger.info("Building tree-sitter languages library...")
            try:
                Language.build_library(
                    LANGUAGES_LIB_PATH,
                    list(repo_paths.values())
                )
                logger.info(f"Successfully built languages library at {LANGUAGES_LIB_PATH}")
            except Exception as e:
                logger.error(f"Failed to build languages library: {e}")
                return False
        
        # Load languages
        for lang in repo_paths.keys():
            try:
                LANGUAGES[lang] = Language(LANGUAGES_LIB_PATH, lang)
                logger.info(f"Successfully loaded {lang} language")
            except Exception as e:
                logger.error(f"Failed to load {lang} language: {e}")
        
        # Create parser
        PARSER = Parser()
        
        return len(LANGUAGES) > 0
        
    except Exception as e:
        logger.error(f"Error setting up tree-sitter languages: {e}")
        return False

# Set up languages on module import
if HAS_TREE_SITTER:
    setup_languages()


class TSParser:
    """
    Tree-sitter parser implementation.
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
        return set(LANGUAGES.keys())
    
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
        if language not in LANGUAGES:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(LANGUAGES.keys()),
                "language": language
            }
        
        # Check if parser is available
        if PARSER is None:
            return {"error": "Tree-sitter parser not initialized"}
        
        try:
            # Set the language
            PARSER.set_language(LANGUAGES[language])
            
            # Ensure code is bytes
            code_bytes = code.encode('utf8') if isinstance(code, str) else code
            
            # Parse the code
            tree = PARSER.parse(code_bytes)
            
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