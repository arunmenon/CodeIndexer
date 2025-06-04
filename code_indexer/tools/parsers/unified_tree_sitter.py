"""
Unified Tree-sitter Parser

Provides a robust parser implementation using the Tree-sitter library that works
with modern versions of tree-sitter (0.20.0+). This implementation handles both
the API style where Language is a class and set_language() is used, and the newer
style where parser.language property is set directly.
"""

import os
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Union, Tuple

# Set up logging
logger = logging.getLogger("unified_tree_sitter_parser")

# Check if tree-sitter is available and get version
try:
    import tree_sitter
    from tree_sitter import Parser
    
    # Try to import Language - it's a class in newer versions and a function in older ones
    if hasattr(tree_sitter, 'Language'):
        from tree_sitter import Language
        HAS_TREE_SITTER = True
    else:
        # In older versions, Language is not imported directly
        HAS_TREE_SITTER = True
        Language = None
    
    # Get version if possible
    if hasattr(tree_sitter, '__version__'):
        TREE_SITTER_VERSION = tree_sitter.__version__
    else:
        TREE_SITTER_VERSION = "unknown"
        
    logger.info(f"Tree-sitter package is available (version: {TREE_SITTER_VERSION})")
    
except ImportError:
    HAS_TREE_SITTER = False
    Language = None
    TREE_SITTER_VERSION = None
    logger.warning("Tree-sitter not available. Install with: pip install tree-sitter")

# Dictionary to store language objects
LANGUAGE_MODULES = {}
LANGUAGE_OBJECTS = {}

# Initialize language packages if available
if HAS_TREE_SITTER:
    # Initialize Python language
    try:
        import tree_sitter_python
        LANGUAGE_MODULES['python'] = tree_sitter_python
        logger.info("tree-sitter-python module loaded")
    except ImportError:
        logger.warning("tree-sitter-python not available. Install with: pip install tree-sitter-python")
    
    # Initialize JavaScript language
    try:
        import tree_sitter_javascript
        LANGUAGE_MODULES['javascript'] = tree_sitter_javascript
        logger.info("tree-sitter-javascript module loaded")
    except ImportError:
        logger.warning("tree-sitter-javascript not available. Install with: pip install tree-sitter-javascript")
    
    # Initialize TypeScript language
    try:
        import tree_sitter_typescript
        LANGUAGE_MODULES['typescript'] = tree_sitter_typescript
        logger.info("tree-sitter-typescript module loaded")
    except ImportError:
        logger.warning("tree-sitter-typescript not available. Install with: pip install tree-sitter-typescript")
    
    # Initialize Java language
    try:
        import tree_sitter_java
        LANGUAGE_MODULES['java'] = tree_sitter_java
        logger.info("tree-sitter-java module loaded")
    except ImportError:
        logger.warning("tree-sitter-java not available. Install with: pip install tree-sitter-java")


def get_language_object(language_name: str) -> Optional[Any]:
    """
    Get the language object for the specified language using appropriate method.
    
    This function handles different ways language objects can be obtained from modules.
    
    Args:
        language_name: Name of the language
        
    Returns:
        Language object or None if not available
    """
    # Check if we already have it
    if language_name in LANGUAGE_OBJECTS:
        return LANGUAGE_OBJECTS[language_name]
    
    # Check if we have the module
    if language_name not in LANGUAGE_MODULES:
        return None
    
    module = LANGUAGE_MODULES[language_name]
    
    # Try different methods to get language
    try:
        # Method 1: Call language() function if it exists
        if hasattr(module, 'language') and callable(module.language):
            try:
                language_obj = module.language()
                LANGUAGE_OBJECTS[language_name] = language_obj
                return language_obj
            except Exception as e:
                logger.warning(f"Error calling {language_name}.language(): {e}")
        
        # Method 2: Use Language attribute if it exists
        if hasattr(module, 'Language'):
            LANGUAGE_OBJECTS[language_name] = module.Language
            return module.Language
        
        # Method 3: Use language attribute if it exists
        if hasattr(module, 'language') and not callable(module.language):
            LANGUAGE_OBJECTS[language_name] = module.language
            return module.language
            
    except Exception as e:
        logger.error(f"Error getting language object for {language_name}: {e}")
    
    return None


class UnifiedTreeSitterParser:
    """
    Unified parser implementation that works with multiple tree-sitter API versions.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Tree-sitter parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self._parser_cache = {}
        
        # Log tree-sitter version
        if HAS_TREE_SITTER:
            logger.info(f"Using tree-sitter version: {TREE_SITTER_VERSION}")
            
        # Try to initialize languages
        self._initialize_languages()
    
    def _initialize_languages(self) -> None:
        """Initialize language parsers."""
        if not HAS_TREE_SITTER:
            logger.warning("Tree-sitter not available, skipping language initialization")
            return
        
        # Process each language module
        for lang_name, module in LANGUAGE_MODULES.items():
            try:
                # Get language object
                language_obj = get_language_object(lang_name)
                
                if language_obj is None:
                    logger.warning(f"Could not get language object for {lang_name}")
                    continue
                
                # Create a parser for this language
                parser = Parser()
                
                # Handle different API styles
                try:
                    # If language_obj is a PyCapsule, we need to wrap it with Language class
                    if hasattr(tree_sitter, 'Language') and not isinstance(language_obj, tree_sitter.Language):
                        # Wrap PyCapsule in Language object
                        language_obj = tree_sitter.Language(language_obj)
                    
                    # Try newer API - set the language property 
                    parser.language = language_obj
                except (AttributeError, TypeError) as e:
                    # Try older API - use set_language method
                    try:
                        if hasattr(parser, 'set_language'):
                            parser.set_language(language_obj)
                        else:
                            logger.error(f"Cannot set language for {lang_name}, incompatible API")
                            continue
                    except Exception as e2:
                        logger.error(f"Failed to set language for {lang_name}: {e2}")
                        continue
                
                # Store in parser cache
                self._parser_cache[lang_name] = parser
                logger.info(f"Successfully initialized parser for {lang_name}")
                
            except Exception as e:
                logger.error(f"Error initializing parser for {lang_name}: {e}")
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return set(self._parser_cache.keys())
        
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
        
        # Get detected language
        detected = extension_map.get(ext, "unknown")
        
        # Check if we support this language
        if detected != "unknown" and detected not in self._parser_cache:
            logger.warning(f"Detected language {detected} from extension, but no parser available")
            return "unknown"
            
        return detected
    
    def parse_code(self, code: str, language: str) -> Dict[str, Any]:
        """Alternative method name for compatibility with SimpleTreeSitterParser.""" 
        return self.parse(code, language, None)
    
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
        if language not in self._parser_cache:
            return {
                "error": f"Language {language} not supported by Tree-sitter",
                "supported_languages": list(self._parser_cache.keys()),
                "language": language
            }
        
        try:
            parser = self._parser_cache[language]
            
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
            
            if language == "unknown" or language not in self._parser_cache:
                return {
                    "error": f"Language {language} not supported or could not be detected",
                    "supported_languages": list(self._parser_cache.keys()),
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