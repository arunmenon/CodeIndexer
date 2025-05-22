"""
Simple Tree-sitter Parser

Uses the tree-sitter bindings available through the pip-installable packages.
This implementation is compatible with the newer tree-sitter Python API and
directly uses the pre-compiled language modules.
"""

import os
import logging
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("basic_tree_sitter_parser")

# Check if tree-sitter is available
try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
    logger.info("Tree-sitter package is available")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Dictionary to store language objects
supported_languages = {}

# Initialize languages if tree-sitter is available
if HAS_TREE_SITTER:
    # Try to initialize Python language
    try:
        import tree_sitter_python
        python_language = Language(tree_sitter_python.language())
        supported_languages['python'] = python_language
        logger.info("Loaded tree-sitter-python language")
    except ImportError:
        logger.warning("tree-sitter-python not available. Install with: pip install tree-sitter-python")
    except Exception as e:
        logger.error(f"Error loading Python language: {e}")
    
    # Try to initialize JavaScript language
    try:
        import tree_sitter_javascript
        javascript_language = Language(tree_sitter_javascript.language())
        supported_languages['javascript'] = javascript_language
        logger.info("Loaded tree-sitter-javascript language")
    except ImportError:
        logger.warning("tree-sitter-javascript not available. Install with: pip install tree-sitter-javascript")
    except Exception as e:
        logger.error(f"Error loading JavaScript language: {e}")
    
    # Try to initialize Java language
    try:
        import tree_sitter_java
        java_language = Language(tree_sitter_java.language())
        supported_languages['java'] = java_language
        logger.info("Loaded tree-sitter-java language")
    except ImportError:
        logger.warning("tree-sitter-java not available. Install with: pip install tree-sitter-java")
    except Exception as e:
        logger.error(f"Error loading Java language: {e}")

# Expose these variables to importers
__all__ = ['BasicTreeSitterParser', 'HAS_TREE_SITTER']


class BasicTreeSitterParser:
    """
    Basic parser implementation using official tree-sitter language packages.
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
        return set(supported_languages.keys())
        
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
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".swift": "swift",
            ".kt": "kotlin"
        }
        
        return extension_map.get(ext, "unknown")
    
    def parse(self, code: str, language: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse code using Tree-sitter.
        
        Args:
            code: Source code to parse
            language: Programming language
            file_path: Optional path to the source file (for metadata)
            
        Returns:
            Dictionary with AST information
        """
        # Check if tree-sitter is available
        if not HAS_TREE_SITTER:
            return {"error": "Tree-sitter not available"}
        
        # Check if language is supported
        if language not in supported_languages:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(supported_languages.keys()),
                "language": language
            }
        
        try:
            # Create a fresh parser for each parse
            parser = Parser()
            
            # Set the language using the language property
            parser.language = supported_languages[language]
            
            # Ensure code is bytes
            code_bytes = code.encode('utf8') if isinstance(code, str) else code
            
            # Parse the code
            tree = parser.parse(code_bytes)
            
            if tree is None:
                raise ValueError("Parsing returned None, check if language is properly loaded")
            
            # Convert the tree to our format
            ast_dict = self._visit_tree(tree.root_node, code_bytes)
            
            # Add metadata
            ast_dict["language"] = language
            ast_dict["parser"] = "tree-sitter"
            
            # Add file path if provided
            if file_path:
                ast_dict["file_path"] = file_path
            
            return ast_dict
            
        except Exception as e:
            logger.error(f"Error parsing {language} code: {e}")
            return {
                "error": f"Failed to parse {language} code using tree-sitter: {str(e)}",
                "language": language
            }
    
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a file using tree-sitter.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            Dictionary with AST information
        """
        if not HAS_TREE_SITTER:
            return {"error": "Tree-sitter not available"}
        
        try:
            # Detect language from file path
            language = self.detect_language(file_path)
            
            if language == "unknown" or language not in supported_languages:
                return {
                    "error": f"Language {language} not supported or could not be detected",
                    "supported_languages": list(supported_languages.keys()),
                    "file_path": file_path
                }
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Parse the code
            return self.parse(code, language, file_path)
            
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return {
                "error": f"Failed to parse file: {str(e)}",
                "file_path": file_path
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