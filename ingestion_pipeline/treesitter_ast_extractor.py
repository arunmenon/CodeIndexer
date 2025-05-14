"""
Tree-sitter AST Extractor

Provides a unified interface for extracting Abstract Syntax Trees (ASTs) from
code in different programming languages using Tree-sitter.
"""

import os
import logging
import json
import tempfile
from typing import Dict, Any, List, Optional, Union, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("treesitter_ast_extractor")

try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    logger.warning("Tree-sitter not available. Please install with: pip install tree-sitter")
    HAS_TREE_SITTER = False


class TreeSitterASTExtractor:
    """
    Unified AST extraction for multiple languages using Tree-sitter.
    
    This class provides a consistent interface to extract ASTs from code files 
    in different languages, returning a standardized JSON-serializable tree structure.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Tree-sitter AST extractor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Default language extensions mapping
        self.language_extensions = self.config.get("language_extensions", {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".hpp": "cpp",
            ".cs": "c_sharp",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".rs": "rust",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".m": "objective_c",
            ".mm": "objective_c",
            ".sh": "bash",
            ".hs": "haskell",
            ".ml": "ocaml",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".xml": "xml",
            ".md": "markdown",
            ".pl": "perl",
            ".pm": "perl",
            ".lua": "lua",
            ".elm": "elm",
            ".clj": "clojure",
            ".ex": "elixir",
            ".exs": "elixir",
            ".erl": "erlang",
            ".proto": "protobuf",
            ".dart": "dart"
        })
        
        # Initialize parsers
        self.parsers = {}
        self.query_cache = {}
        
        # Set up Tree-sitter
        if HAS_TREE_SITTER:
            self._setup_tree_sitter()
        
    def _setup_tree_sitter(self):
        """Set up Tree-sitter and load language libraries."""
        try:
            # Determine paths for Tree-sitter language libraries
            lib_dir = self.config.get("tree_sitter_lib_dir")
            
            # If not specified, check common locations or create temporary directory
            if not lib_dir:
                for path in [
                    os.path.join(os.path.dirname(__file__), "tree-sitter-libs"),
                    os.path.expanduser("~/.tree-sitter-libs"),
                    "/usr/local/share/tree-sitter-libs",
                ]:
                    if os.path.exists(path):
                        lib_dir = path
                        break
                
                if not lib_dir:
                    # Create temporary directory for language libraries
                    lib_dir = tempfile.mkdtemp(prefix="tree-sitter-libs-")
                    logger.info(f"Created temporary directory for Tree-sitter libraries: {lib_dir}")
            
            # Get list of languages to load
            languages_to_load = self.config.get("languages", [
                "python", "javascript", "typescript", "java", "c", "cpp", "c_sharp", 
                "go", "ruby", "php", "rust", "bash", "json", "html", "css"
            ])
            
            # Load languages from binary files or build them if necessary
            for language in languages_to_load:
                try:
                    self._load_language(language, lib_dir)
                except Exception as e:
                    logger.warning(f"Failed to load {language} parser: {e}")
            
            logger.info(f"Loaded Tree-sitter parsers for: {', '.join(self.parsers.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to set up Tree-sitter: {e}")
    
    def _load_language(self, language_name: str, lib_dir: str):
        """
        Load a Tree-sitter language parser.
        
        Args:
            language_name: Name of the language
            lib_dir: Directory for language libraries
        """
        language_lib_path = os.path.join(lib_dir, f"{language_name}.so")
        
        try:
            # Try to load existing language library
            language = Language(language_lib_path, language_name)
            
            # Create parser for this language
            parser = Parser()
            parser.set_language(language)
            
            # Store parser
            self.parsers[language_name] = parser
            logger.info(f"Loaded Tree-sitter parser for {language_name}")
            
            # Try to pre-cache some common queries
            self._cache_common_queries(language, language_name)
            
        except Exception as e:
            # Language library doesn't exist or is invalid
            logger.warning(f"Could not load {language_name} parser: {e}")
            if os.path.exists(language_lib_path):
                logger.warning(f"Library exists but may be incompatible: {language_lib_path}")
            else:
                logger.warning(f"Library not found: {language_lib_path}")
            
            raise e
    
    def _cache_common_queries(self, language, language_name):
        """Cache common queries for a language."""
        try:
            # Define common queries based on language
            queries = {}
            
            if language_name == "python":
                queries["classes"] = """
                (class_definition
                  name: (identifier) @class.name
                  body: (block . (expression_statement (string) @class.docstring)?)
                ) @class.definition
                """
                
                queries["functions"] = """
                (function_definition
                  name: (identifier) @function.name
                  parameters: (parameters) @function.params
                  body: (block . (expression_statement (string) @function.docstring)?)
                ) @function.definition
                """
            
            elif language_name in ["javascript", "typescript"]:
                queries["classes"] = """
                (class_declaration
                  name: (identifier) @class.name
                  body: (class_body)
                ) @class.definition
                """
                
                queries["functions"] = """
                (function_declaration
                  name: (identifier) @function.name
                  parameters: (formal_parameters) @function.params
                ) @function.definition
                
                (method_definition
                  name: (property_identifier) @method.name
                  parameters: (formal_parameters) @method.params
                ) @method.definition
                """
            
            # Compile and cache queries
            for query_name, query_string in queries.items():
                query_key = f"{language_name}:{query_name}"
                try:
                    compiled_query = language.query(query_string)
                    self.query_cache[query_key] = compiled_query
                except Exception as e:
                    logger.warning(f"Failed to compile query '{query_name}' for {language_name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to cache queries for {language_name}: {e}")
    
    def extract_ast(self, code: str, language: Optional[str] = None, 
                  file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract AST from code.
        
        Args:
            code: Source code
            language: Programming language (optional, will be detected if not provided)
            file_path: Path to the source file (optional, used for language detection)
            
        Returns:
            Dictionary containing the AST in a standardized format
        """
        if not HAS_TREE_SITTER:
            return {
                "error": "Tree-sitter not available",
                "type": "error",
                "message": "Please install tree-sitter with: pip install tree-sitter"
            }
        
        # Detect language if not provided
        if not language and file_path:
            language = self._detect_language(file_path)
        
        # If still no language, try to detect from code
        if not language:
            language = self._detect_language_from_code(code)
            logger.info(f"Detected language from code: {language}")
        
        # Extract AST
        try:
            parser = self.parsers.get(language)
            if parser:
                # Parse code with Tree-sitter
                tree = parser.parse(bytes(code, "utf8"))
                
                # Convert to our standardized format
                ast_dict = self._convert_tree_to_dict(tree.root_node, language)
                
                # Add metadata
                ast_dict["language"] = language
                ast_dict["type"] = "ast"
                ast_dict["parser"] = "tree-sitter"
                if file_path:
                    ast_dict["file_path"] = file_path
                
                return ast_dict
            else:
                logger.warning(f"No parser available for {language}")
                return {
                    "error": f"No parser available for {language}",
                    "type": "error",
                    "language": language
                }
        except Exception as e:
            logger.error(f"Failed to extract AST: {e}")
            return {
                "error": str(e),
                "type": "error",
                "language": language
            }
    
    def extract_ast_from_file(self, file_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract AST from a file.
        
        Args:
            file_path: Path to the source file
            language: Programming language (optional, will be detected if not provided)
            
        Returns:
            Dictionary containing the AST in a standardized format
        """
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            
            # Detect language if not provided
            if not language:
                language = self._detect_language(file_path)
            
            # Extract AST
            return self.extract_ast(code, language, file_path)
            
        except Exception as e:
            logger.error(f"Failed to extract AST from file {file_path}: {e}")
            return {
                "error": str(e),
                "file_path": file_path,
                "language": language or "unknown"
            }
    
    def _detect_language(self, file_path: str) -> str:
        """
        Detect programming language from file path.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Detected language or 'unknown'
        """
        ext = os.path.splitext(file_path)[1].lower()
        language = self.language_extensions.get(ext, "unknown")
        return language
    
    def _detect_language_from_code(self, code: str) -> str:
        """
        Attempt to detect programming language from code content.
        
        Args:
            code: Source code
            
        Returns:
            Detected language or 'unknown'
        """
        # Simple heuristics to detect language
        if code.strip().startswith("<?php"):
            return "php"
        elif "function" in code and ("{" in code and "}" in code) and (";" in code):
            if "import React" in code or "jsx" in code:
                return "javascript"  # Likely JSX/React
            return "javascript"
        elif "def " in code and ":" in code and "import " in code:
            return "python"
        elif "class " in code and "{" in code and "public" in code and ";" in code:
            return "java"
        elif "package " in code and "import" in code and "func " in code:
            return "go"
        elif "<html" in code.lower() and "<body" in code.lower():
            return "html"
        elif "@interface" in code or "@implementation" in code:
            return "objective_c"
        elif "fn " in code and "->" in code and "let " in code:
            return "rust"
        
        # Default to unknown
        return "unknown"
    
    def _convert_tree_to_dict(self, node, language: str) -> Dict[str, Any]:
        """
        Convert a Tree-sitter node to a dictionary.
        
        Args:
            node: Tree-sitter node
            language: Programming language
            
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
                    self._convert_tree_to_dict(child, language)
                    for child in node.children
                ]
        
        return result
    
    def extract_entities(self, ast_dict: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract entities (classes, functions, etc.) from an AST.
        
        Args:
            ast_dict: AST dictionary
            
        Returns:
            Dictionary with extracted entities
        """
        language = ast_dict.get("language", "unknown")
        entities = {
            "classes": [],
            "functions": [],
            "methods": [],
            "imports": []
        }
        
        # Extract entities using language-specific strategies
        if language == "python":
            entities = self._extract_python_entities(ast_dict)
        elif language in ["javascript", "typescript"]:
            entities = self._extract_js_ts_entities(ast_dict)
        elif language == "java":
            entities = self._extract_java_entities(ast_dict)
        # Add more languages as needed
        
        return entities
    
    def _extract_python_entities(self, ast_dict: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract entities from Python AST."""
        entities = {
            "classes": [],
            "functions": [],
            "methods": [],
            "imports": []
        }
        
        # Use cached queries if available
        classes_query = self.query_cache.get("python:classes")
        functions_query = self.query_cache.get("python:functions")
        
        # Extract classes and functions using the node visitor pattern
        def visit_node(node, parent_class=None):
            if not isinstance(node, dict):
                return
            
            node_type = node.get("type", "")
            
            # Extract classes
            if node_type == "class_definition":
                class_info = self._extract_python_class(node)
                entities["classes"].append(class_info)
                
                # Process class methods with class context
                for child in node.get("children", []):
                    visit_node(child, class_info)
                
            # Extract functions/methods
            elif node_type == "function_definition":
                if parent_class:
                    # This is a method
                    method_info = self._extract_python_function(node)
                    method_info["class_name"] = parent_class.get("name")
                    method_info["is_method"] = True
                    entities["methods"].append(method_info)
                else:
                    # This is a standalone function
                    function_info = self._extract_python_function(node)
                    entities["functions"].append(function_info)
            
            # Extract imports
            elif node_type == "import_statement":
                import_info = self._extract_python_import(node)
                if import_info:
                    entities["imports"].append(import_info)
            elif node_type == "import_from_statement":
                import_info = self._extract_python_import_from(node)
                if import_info:
                    entities["imports"].append(import_info)
            
            # Recursively process children
            for child in node.get("children", []):
                if parent_class is None or node_type != "class_definition":
                    visit_node(child, parent_class)
        
        # Start processing from the root
        if "root" in ast_dict:
            visit_node(ast_dict["root"])
        
        return entities
    
    def _extract_python_class(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information about a Python class."""
        class_info = {
            "name": "",
            "start_line": node.get("start_position", {}).get("row", 0) + 1,
            "end_line": node.get("end_position", {}).get("row", 0) + 1,
            "docstring": "",
            "parents": []
        }
        
        # Extract class name
        for child in node.get("children", []):
            if child.get("type") == "identifier":
                class_info["name"] = child.get("text", "")
            elif child.get("type") == "argument_list":
                # Extract parents (base classes)
                for arg in child.get("children", []):
                    if arg.get("type") == "identifier":
                        class_info["parents"].append(arg.get("text", ""))
        
        # Look for docstring (first string expression in body)
        body = None
        for child in node.get("children", []):
            if child.get("type") == "block":
                body = child
                break
        
        if body:
            for child in body.get("children", []):
                if child.get("type") == "expression_statement":
                    for expr_child in child.get("children", []):
                        if expr_child.get("type") == "string":
                            class_info["docstring"] = expr_child.get("text", "")
                            break
                    if class_info["docstring"]:
                        break
        
        return class_info
    
    def _extract_python_function(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information about a Python function."""
        function_info = {
            "name": "",
            "start_line": node.get("start_position", {}).get("row", 0) + 1,
            "end_line": node.get("end_position", {}).get("row", 0) + 1,
            "params": [],
            "docstring": "",
            "return_type": None,
            "is_method": False
        }
        
        # Extract function name
        for child in node.get("children", []):
            if child.get("type") == "identifier":
                function_info["name"] = child.get("text", "")
            elif child.get("type") == "parameters":
                # Extract parameters
                for param in child.get("children", []):
                    if param.get("type") == "identifier":
                        function_info["params"].append(param.get("text", ""))
        
        # Look for docstring (first string expression in body)
        body = None
        for child in node.get("children", []):
            if child.get("type") == "block":
                body = child
                break
        
        if body:
            for child in body.get("children", []):
                if child.get("type") == "expression_statement":
                    for expr_child in child.get("children", []):
                        if expr_child.get("type") == "string":
                            function_info["docstring"] = expr_child.get("text", "")
                            break
                    if function_info["docstring"]:
                        break
        
        return function_info
    
    def _extract_python_import(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information about a Python import statement."""
        import_info = {
            "type": "import",
            "names": []
        }
        
        for child in node.get("children", []):
            if child.get("type") == "dotted_name":
                name = ".".join([n.get("text", "") for n in child.get("children", []) 
                                if n.get("type") == "identifier"])
                import_info["names"].append({"name": name})
            
        return import_info if import_info["names"] else None
    
    def _extract_python_import_from(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information about a Python import from statement."""
        import_info = {
            "type": "import_from",
            "module": "",
            "names": []
        }
        
        for child in node.get("children", []):
            if child.get("type") == "dotted_name":
                module = ".".join([n.get("text", "") for n in child.get("children", []) 
                                  if n.get("type") == "identifier"])
                import_info["module"] = module
            elif child.get("type") == "import_statement":
                # Extract imported names
                for subchild in child.get("children", []):
                    if subchild.get("type") == "identifier":
                        import_info["names"].append({"name": subchild.get("text", "")})
        
        return import_info if import_info["module"] and import_info["names"] else None
    
    def _extract_js_ts_entities(self, ast_dict: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract entities from JavaScript/TypeScript AST."""
        # Similar implementation to Python but for JS/TS
        # Implementation details would depend on JS/TS Tree-sitter structure
        return {
            "classes": [],
            "functions": [],
            "methods": [],
            "imports": []
        }
    
    def _extract_java_entities(self, ast_dict: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract entities from Java AST."""
        # Similar implementation to Python but for Java
        # Implementation details would depend on Java Tree-sitter structure
        return {
            "classes": [],
            "functions": [],
            "methods": [],
            "imports": []
        }


# Factory function for backward compatibility
def create_tree_sitter_extractor(config: Dict[str, Any] = None) -> TreeSitterASTExtractor:
    """Create a Tree-sitter AST extractor with the given configuration."""
    return TreeSitterASTExtractor(config)