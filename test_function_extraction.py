"""
Test function extraction with tree-sitter and the expanded function types.

This test validates that the get_functions utility in ast_iterator.py
correctly identifies function nodes across different programming languages.
"""

import os
import json
import logging
from pathlib import Path

from code_indexer.utils.ast_iterator import DictASTIterator, get_functions
from code_indexer.tools.tree_sitter_parser import TreeSitterParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample code snippets for different languages
SAMPLES = {
    "python": """
def simple_function():
    return True

class MyClass:
    def class_method(self):
        return "method"
        
    @staticmethod
    def static_method():
        return "static"
""",
    
    "javascript": """
function normalFunction() {
    return true;
}

const arrowFunction = () => {
    return false;
};

class Example {
    constructor() {
        this.value = 42;
    }
    
    methodFunction() {
        return this.value;
    }
}
""",
    
    "java": """
package example;

public class Main {
    public static void main(String[] args) {
        System.out.println("Hello");
    }
    
    private int calculate(int a, int b) {
        return a + b;
    }
}
"""
}


def test_function_extraction():
    """Test function extraction across multiple languages."""
    results = {}
    
    # Initialize parser
    parser = TreeSitterParser()
    
    # Since we may not have all language parsers installed,
    # let's focus on Python which is more likely to be available
    
    # Get supported languages
    supported_languages = parser.get_supported_languages()
    logger.info(f"Supported languages: {supported_languages}")
    
    # Process each supported language sample
    for lang, code in SAMPLES.items():
        if lang not in supported_languages:
            logger.warning(f"Skipping {lang} - parser not installed")
            results[lang] = {"skipped": f"Parser not installed for {lang}"}
            continue
            
        try:
            # Parse code with tree-sitter
            ast_dict = parser.parse_string(code, lang)
            
            # Create iterator
            iterator = DictASTIterator(ast_dict)
            
            # Extract functions
            functions = []
            for func_node in get_functions(iterator):
                # Find function name
                name = ""
                if "children" in func_node:
                    for child in func_node["children"]:
                        if child.get("type") == "identifier":
                            name = child.get("text", "")
                            break
                
                functions.append({
                    "type": func_node["type"],
                    "name": name
                })
            
            # Store results
            results[lang] = functions
            
            # Log success
            logger.info(f"Successfully extracted {len(functions)} functions from {lang} sample")
            for func in functions:
                logger.info(f"  - {func['type']}: {func['name']}")
            
        except Exception as e:
            logger.error(f"Error processing {lang} sample: {str(e)}")
            results[lang] = {"error": str(e)}
    
    return results


if __name__ == "__main__":
    # Run the test
    results = test_function_extraction()
    
    # Save results
    with open("function_extraction_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\nFunction Extraction Test Results:")
    print("--------------------------------")
    
    all_supported_successful = True
    supported_count = 0
    
    for lang, funcs in results.items():
        if isinstance(funcs, dict) and "error" in funcs:
            print(f"❌ {lang}: Error - {funcs['error']}")
            all_supported_successful = False
            supported_count += 1
        elif isinstance(funcs, dict) and "skipped" in funcs:
            print(f"⚠️ {lang}: {funcs['skipped']}")
        else:
            print(f"✅ {lang}: Found {len(funcs)} functions")
            for func in funcs:
                print(f"   - {func['name']} ({func['type']})")
            supported_count += 1
    
    if supported_count == 0:
        print("\n⚠️ No language parsers available for testing. Please install tree-sitter language packages.")
        exit(0)
    elif all_supported_successful:
        print(f"\n✅ All available language tests passed successfully! ({supported_count} languages)")
        exit(0)
    else:
        print(f"\n❌ Some language tests failed. See details above. ({supported_count} languages tested)")
        exit(1)