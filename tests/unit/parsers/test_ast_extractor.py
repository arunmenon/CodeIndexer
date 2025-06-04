#!/usr/bin/env python
"""
Test the AST extractor with tree-sitter.
"""

import os
import logging
import json
from pathlib import Path
from code_indexer.tools.ast_extractor import ASTExtractorTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Configure the AST extractor
    config = {
        "use_tree_sitter": True,
        "parser_name": "simple_tree_sitter",
        "tree_sitter_config": {
            "languages": ["python", "javascript", "java"]
        }
    }

    # Make sure to use the simple tree-sitter parser
    os.environ["TREE_SITTER_PARSER"] = "simple"
    
    # Create the AST extractor
    extractor = ASTExtractorTool(config)
    
    # Test with a simple Python file
    test_code = """
def hello_world():
    print("Hello, world!")
    
if __name__ == "__main__":
    hello_world()
"""
    
    # Extract AST directly from code
    logger.info("Extracting AST from Python code...")
    ast_dict = extractor.extract_ast(test_code, language="python", file_path="test.py")
    
    # Print the result
    print(json.dumps(ast_dict, indent=2))
    
if __name__ == "__main__":
    main()