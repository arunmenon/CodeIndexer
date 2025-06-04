"""
Simple Parser Implementation

This is a minimal parser that supports multiple languages by recognizing 
basic syntax structures. It doesn't depend on external libraries but provides
enough information to recognize code constructs.
"""

import os
import re
import logging
from typing import Dict, Any, List, Set, Optional

# Set up logging
logger = logging.getLogger("simple_parser")

class SimpleParser:
    """
    A simple parser implementation that recognizes basic syntax structures.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the simple parser.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        return {"python", "javascript", "java"}
    
    def parse(self, code: str, language: str) -> Dict[str, Any]:
        """
        Parse code using simple pattern recognition.
        
        Args:
            code: Source code to parse
            language: Programming language
            
        Returns:
            Dictionary with AST information
        """
        # Check if language is supported
        if language not in self.supported_languages():
            return {
                "error": f"Language {language} not supported",
                "supported_languages": list(self.supported_languages()),
                "language": language
            }
        
        try:
            # Parse based on language
            if language == "python":
                ast_dict = self._parse_python(code)
            elif language == "javascript":
                ast_dict = self._parse_javascript(code)
            elif language == "java":
                ast_dict = self._parse_java(code)
            else:
                return {"error": f"Language {language} not supported"}
            
            # Add metadata
            ast_dict["language"] = language
            ast_dict["parser"] = "simple_parser"
            
            return ast_dict
            
        except Exception as e:
            logger.error(f"Error parsing {language} code: {e}")
            return {
                "error": f"Failed to parse {language} code: {str(e)}",
                "language": language
            }
    
    def _parse_python(self, code: str) -> Dict[str, Any]:
        """Parse Python code."""
        # Extract classes
        classes = []
        class_pattern = r"class\s+(\w+)(?:\s*\(\s*(\w+)\s*\))?:"
        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)
            parent_class = match.group(2)
            classes.append({
                "name": class_name,
                "bases": [parent_class] if parent_class else [],
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract functions
        functions = []
        func_pattern = r"def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?:"
        for match in re.finditer(func_pattern, code):
            func_name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3)
            
            # Parse parameters
            params = []
            if params_str:
                params = [p.strip() for p in params_str.split(',')]
                # Remove self or cls from parameters in methods
                if params and params[0] in ('self', 'cls'):
                    params = params[1:]
            
            functions.append({
                "name": func_name,
                "parameters": params,
                "return_type": return_type.strip() if return_type else None,
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract imports
        imports = []
        import_pattern = r"(?:from\s+([\w.]+)\s+)?import\s+([\w,\s.]+)(?:\s+as\s+(\w+))?"
        for match in re.finditer(import_pattern, code):
            module = match.group(1)
            names = match.group(2)
            alias = match.group(3)
            
            imports.append({
                "text": match.group(0),
                "module": module,
                "names": [n.strip() for n in names.split(',')],
                "alias": alias,
                "start": match.start(),
                "end": match.end()
            })
        
        # Create the AST
        return {
            "type": "module",
            "entities": {
                "classes": classes,
                "functions": functions,
                "imports": imports
            },
            "code_length": len(code),
            "lines": code.count('\n') + 1
        }
    
    def _parse_javascript(self, code: str) -> Dict[str, Any]:
        """Parse JavaScript code."""
        # Extract classes
        classes = []
        class_pattern = r"class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{"
        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)
            parent_class = match.group(2)
            classes.append({
                "name": class_name,
                "bases": [parent_class] if parent_class else [],
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract functions
        functions = []
        func_pattern = r"(?:function|async function)\s+(\w+)\s*\(([^)]*)\)"
        for match in re.finditer(func_pattern, code):
            func_name = match.group(1)
            params_str = match.group(2)
            
            # Parse parameters
            params = []
            if params_str:
                params = [p.strip() for p in params_str.split(',')]
            
            functions.append({
                "name": func_name,
                "parameters": params,
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract methods
        methods = []
        method_pattern = r"(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{"
        for match in re.finditer(method_pattern, code):
            method_name = match.group(1)
            params_str = match.group(2)
            
            # Exclude if matched string is preceded by 'function' (already caught)
            prev_chars = code[max(0, match.start() - 9):match.start()]
            if 'function' in prev_chars:
                continue
            
            # Parse parameters
            params = []
            if params_str:
                params = [p.strip() for p in params_str.split(',')]
            
            methods.append({
                "name": method_name,
                "parameters": params,
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract imports
        imports = []
        import_pattern = r"import\s+(?:\*\s+as\s+(\w+)|{\s*([^}]+)\s*}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]"
        for match in re.finditer(import_pattern, code):
            namespace = match.group(1)
            named_imports = match.group(2)
            default_import = match.group(3)
            module = match.group(4)
            
            imports.append({
                "text": match.group(0),
                "module": module,
                "namespace": namespace,
                "named_imports": [n.strip() for n in named_imports.split(',')] if named_imports else [],
                "default_import": default_import,
                "start": match.start(),
                "end": match.end()
            })
        
        # Create the AST
        return {
            "type": "program",
            "entities": {
                "classes": classes,
                "functions": functions,
                "methods": methods,
                "imports": imports
            },
            "code_length": len(code),
            "lines": code.count('\n') + 1
        }
    
    def _parse_java(self, code: str) -> Dict[str, Any]:
        """Parse Java code."""
        # Extract classes
        classes = []
        class_pattern = r"(?:public|private|protected|)\s+(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?\s*\{"
        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)
            parent_class = match.group(2)
            interfaces_str = match.group(3)
            
            interfaces = []
            if interfaces_str:
                interfaces = [i.strip() for i in interfaces_str.split(',')]
            
            classes.append({
                "name": class_name,
                "bases": [parent_class] if parent_class else [],
                "interfaces": interfaces,
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract methods
        methods = []
        method_pattern = r"(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:abstract\s+)?(?:[\w<>[\],\s]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+([^{]+))?\s*(?:\{|;)"
        for match in re.finditer(method_pattern, code):
            method_name = match.group(1)
            params_str = match.group(2)
            throws_str = match.group(3)
            
            # Parse parameters
            params = []
            if params_str:
                # Java parameters include type, so we need to extract just the parameter names
                param_pattern = r"(?:final\s+)?[\w<>[\],\s]+\s+(\w+)(?:\s*=\s*[^,]+)?"
                for param_match in re.finditer(param_pattern, params_str):
                    params.append(param_match.group(1))
            
            throws = []
            if throws_str:
                throws = [t.strip() for t in throws_str.split(',')]
            
            methods.append({
                "name": method_name,
                "parameters": params,
                "throws": throws,
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract imports
        imports = []
        import_pattern = r"import\s+(?:static\s+)?([\w.]+)(?:\.\*)?;"
        for match in re.finditer(import_pattern, code):
            package = match.group(1)
            
            imports.append({
                "text": match.group(0),
                "package": package,
                "is_wildcard": "*" in match.group(0),
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract package
        package = None
        package_pattern = r"package\s+([\w.]+);"
        package_match = re.search(package_pattern, code)
        if package_match:
            package = package_match.group(1)
        
        # Create the AST
        return {
            "type": "compilation_unit",
            "package": package,
            "entities": {
                "classes": classes,
                "methods": methods,
                "imports": imports
            },
            "code_length": len(code),
            "lines": code.count('\n') + 1
        }