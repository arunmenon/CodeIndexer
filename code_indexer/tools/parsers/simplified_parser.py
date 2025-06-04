"""
Simplified Tree-sitter Parser

A simplified approach that uses subprocess to run a small Python script
that utilizes tree-sitter to parse code and return a JSON representation.
"""

import os
import json
import logging
import tempfile
import subprocess
from typing import Dict, Any, Set

# Set up logging
logger = logging.getLogger("simplified_parser")

class SimplifiedParser:
    """
    A simplified parser that uses a subprocess to run tree-sitter.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the parser.
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}
    
    def supported_languages(self) -> Set[str]:
        """Return the set of supported languages."""
        # We'll try to support these languages
        return {"python", "javascript", "java"}
    
    def parse(self, code: str, language: str) -> Dict[str, Any]:
        """
        Parse code using a subprocess that runs tree-sitter.
        
        Args:
            code: Source code to parse
            language: Programming language
            
        Returns:
            Dictionary with AST information
        """
        if language not in self.supported_languages():
            return {
                "error": f"Language {language} not supported",
                "supported_languages": list(self.supported_languages())
            }
        
        try:
            # Create a temporary file for the code
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{language}', delete=False) as code_file:
                code_file.write(code)
                code_path = code_file.name
            
            # Create a Python script to parse the code
            script = f'''
import sys
import json

try:
    import tree_sitter
    parser = tree_sitter.Parser()
    
    # Load the appropriate language
    if "{language}" == "python":
        import tree_sitter_python
        parser.language = tree_sitter_python.language()
    elif "{language}" == "javascript":
        import tree_sitter_javascript
        parser.language = tree_sitter_javascript.language()
    elif "{language}" == "java":
        import tree_sitter_java
        parser.language = tree_sitter_java.language()
    
    # Read the file
    with open("{code_path}", "rb") as f:
        code_bytes = f.read()
    
    # Parse the code
    tree = parser.parse(code_bytes)
    
    # Convert the tree to a dictionary
    def node_to_dict(node):
        result = {{
            "type": node.type,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
            "start_point": {{"row": node.start_point[0], "column": node.start_point[1]}},
            "end_point": {{"row": node.end_point[0], "column": node.end_point[1]}},
        }}
        
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
                child_dict = node_to_dict(node.children[i])
                result["children"].append(child_dict)
        
        return result
    
    # Convert the tree to JSON
    result = {{
        "type": "module",
        "language": "{language}",
        "parser": "tree-sitter",
        "root": node_to_dict(tree.root_node)
    }}
    
    # Print the result as JSON
    print(json.dumps(result))
    
except ImportError as e:
    error = {{"error": f"ImportError: {{str(e)}}"}}
    print(json.dumps(error))
except Exception as e:
    error = {{"error": f"Error: {{str(e)}}"}}
    print(json.dumps(error))
'''
            
            # Create a temporary file for the script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
                script_file.write(script)
                script_path = script_file.name
            
            # Run the script in a subprocess
            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                check=False  # Don't raise an exception on non-zero exit
            )
            
            # Clean up temporary files
            os.unlink(code_path)
            os.unlink(script_path)
            
            # Check if the subprocess ran successfully
            if result.returncode != 0:
                return {
                    "error": f"Failed to run parser subprocess: {result.stderr}",
                    "language": language
                }
            
            # Parse the JSON result
            try:
                ast_dict = json.loads(result.stdout)
                return ast_dict
            except json.JSONDecodeError:
                return {
                    "error": f"Failed to parse JSON output: {result.stdout}",
                    "language": language
                }
            
        except Exception as e:
            logger.error(f"Error parsing {language} code: {e}")
            return {
                "error": f"Failed to parse {language} code: {str(e)}",
                "language": language
            }