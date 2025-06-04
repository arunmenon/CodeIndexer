"""
Tree-Sitter Parser

A standalone Tree-Sitter parser implementation with no fallbacks or dependencies
on other parts of the codebase.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union, Tuple

# Configure logging
logger = logging.getLogger(__name__)

class TreeSitterParser:
    """
    Standalone Tree-Sitter parser that requires tree-sitter to be installed.
    
    No fallbacks or dependencies on other parts of the codebase.
    """
    
    def __init__(self, languages: Optional[List[str]] = None):
        """
        Initialize the Tree-Sitter parser.
        
        Args:
            languages: List of languages to initialize, or None for default set
                       (python, javascript, typescript, java)
        
        Raises:
            ImportError: If tree-sitter is not installed
        """
        # Import tree-sitter - will raise ImportError if not available
        try:
            import tree_sitter
            self.tree_sitter = tree_sitter
        except ImportError:
            raise ImportError(
                "Tree-sitter is not installed. Please install with: "
                "pip install tree-sitter tree-sitter-python tree-sitter-javascript"
            )
        
        # Initialize parsers
        self.parsers = {}
        
        # Default languages if none specified
        if languages is None:
            languages = ["python", "javascript", "typescript", "java"]
        
        # Map of language names to their module names
        self.language_modules = {
            "python": "tree_sitter_python",
            "javascript": "tree_sitter_javascript",
            "typescript": "tree_sitter_javascript",  # TypeScript uses JavaScript grammar
            "java": "tree_sitter_java"
        }
        
        # Load each language using a simpler approach
        for lang in languages:
            if self._load_language_direct(lang):
                logger.info(f"Successfully loaded {lang} parser")
    
    def _load_language_direct(self, language_name: str) -> bool:
        """
        Load a language directly without the complexities of the previous approach.
        This simpler approach should work with tree-sitter 0.20.0+
        
        Args:
            language_name: Name of the language to load
            
        Returns:
            True if language was loaded successfully, False otherwise
        """
        try:
            # Check if this language is supported
            if language_name not in self.language_modules:
                logger.warning(f"Language {language_name} not supported")
                return False
            
            # Get the module name for this language
            module_name = self.language_modules[language_name]
            
            # Create a fresh parser for this language
            parser = self.tree_sitter.Parser()
            
            # Import the language module
            try:
                module = __import__(module_name)
                
                # Get the language data
                # tree_sitter_python.language() returns a pointer to the language data
                language_data = module.language()
                
                # Create a language object from the data
                language = self.tree_sitter.Language(language_data)
                
                # Associate the language with the parser
                parser.language = language
                
                # Store the parser
                self.parsers[language_name] = parser
                return True
                
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to import {module_name}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error loading {language_name} parser: {e}")
            return False
    
    def get_supported_languages(self) -> Set[str]:
        """
        Get the set of supported languages.
        
        Returns:
            Set of language names that are currently supported
        """
        return set(self.parsers.keys())
    
    def parse_file(self, file_path: Union[str, Path], language: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse a file into an AST.
        
        Args:
            file_path: Path to the file to parse
            language: Language name, or None to detect from file extension
            
        Returns:
            Dictionary containing the AST
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the language is not supported or can't be detected
        """
        # Convert to Path object
        path = Path(file_path)
        
        # Check if file exists
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Detect language if not provided
        if language is None:
            language = self._detect_language(path)
            if language is None:
                raise ValueError(f"Could not detect language for file: {file_path}")
        
        # Check if language is supported
        if language not in self.parsers:
            raise ValueError(f"Language not supported: {language}")
        
        # Read file content
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            code = f.read()
        
        # Parse code
        ast_dict = self.parse_string(code, language)
        
        # Add file path to AST
        ast_dict["file_path"] = str(path)
        
        return ast_dict
    
    def parse_string(self, code: str, language: str) -> Dict[str, Any]:
        """
        Parse a code string into an AST.
        
        Args:
            code: Source code to parse
            language: Programming language name
            
        Returns:
            Dictionary containing the AST
            
        Raises:
            ValueError: If the language is not supported
        """
        # Check if language is supported
        if language not in self.parsers:
            raise ValueError(f"Language not supported: {language}")
        
        # Get parser for this language
        parser = self.parsers[language]
        
        # Parse the code
        try:
            # Convert code to bytes
            code_bytes = bytes(code, 'utf-8')
            
            # Parse code - we use set_language consistently now
            tree = parser.parse(code_bytes)
            
            # Convert to dictionary representation
            ast_dict = {
                "type": "root",
                "language": language,
                "parser": "tree-sitter"
            }
            
            # Convert tree to dictionary
            root_node = self._node_to_dict(tree.root_node, code)
            ast_dict["root"] = root_node
            
            return ast_dict
            
        except Exception as e:
            logger.error(f"Error parsing code with tree-sitter: {e}")
            # Return a minimal AST with error information
            return {
                "type": "root",
                "language": language,
                "parser": "tree-sitter",
                "error": str(e),
                "root": {"type": "error", "text": "Failed to parse code"}
            }
    
    def _node_to_dict(self, node, source_code: str) -> Dict[str, Any]:
        """
        Convert a Tree-sitter node to a dictionary.
        
        Args:
            node: Tree-sitter node
            source_code: Original source code
            
        Returns:
            Dictionary representation of the node
        """
        # Create a standardized node representation
        result = {
            "type": node.type,
            "start_point": {
                "row": node.start_point[0],
                "column": node.start_point[1]
            },
            "end_point": {
                "row": node.end_point[0],
                "column": node.end_point[1]
            }
        }
        
        # Extract text for leaf nodes
        if len(node.children) == 0:
            try:
                result["text"] = node.text.decode('utf-8')
            except:
                # Handle binary data
                result["text"] = str(node.text)
        
        # Process children
        if node.children:
            result["children"] = [
                self._node_to_dict(child, source_code)
                for child in node.children
            ]
        
        return result
    
    def _detect_language(self, file_path: Path) -> Optional[str]:
        """
        Detect language from file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Language name or None if unknown
        """
        # Map file extensions to languages
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java"
        }
        
        suffix = file_path.suffix.lower()
        return extension_map.get(suffix)