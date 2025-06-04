#!/usr/bin/env python3
"""
Test script for the BasicTreeSitterParser implementation.

This script demonstrates how to use the BasicTreeSitterParser to parse code in
multiple languages: Python, JavaScript, and Java.
"""

import os
import sys
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our parser
from code_indexer.tools.parsers.basic_tree_sitter import BasicTreeSitterParser, HAS_TREE_SITTER

def test_python_parsing(parser):
    """Test parsing Python code."""
    print("\n===== TESTING PYTHON PARSING =====")
    
    # Sample Python code to parse
    python_code = """
import os
import sys
from typing import Dict, List, Optional

class BaseClass:
    \"\"\"Base class for demonstration.\"\"\"
    
    def __init__(self, name: str):
        self.name = name
    
    def get_name(self) -> str:
        return self.name

class ChildClass(BaseClass):
    \"\"\"Child class that extends BaseClass.\"\"\"
    
    def __init__(self, name: str, value: int):
        super().__init__(name)
        self.value = value
    
    def get_value(self) -> int:
        return self.value

def main():
    \"\"\"Main function.\"\"\"
    base = BaseClass("Base")
    child = ChildClass("Child", 42)
    
    print(f"Base name: {base.get_name()}")
    print(f"Child name: {child.get_name()}, value: {child.get_value()}")

if __name__ == "__main__":
    main()
"""

    # Parse the Python code
    result = parser.parse(python_code, "python")
    
    # Check if parsing was successful
    if "error" in result:
        logging.error(f"Python parsing failed: {result['error']}")
        return False
    
    # Print AST structure
    print(f"Python AST root type: {result['type']}")
    print(f"Python AST node count: {len(result.get('children', []))} child nodes")
    
    return True

def test_javascript_parsing(parser):
    """Test parsing JavaScript code."""
    print("\n===== TESTING JAVASCRIPT PARSING =====")
    
    # Sample JavaScript code
    js_code = """
// Sample JavaScript code
function greet(name) {
    console.log(`Hello, ${name}!`);
    return `Greeting sent to ${name}`;
}

class Person {
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    
    sayHello() {
        return greet(this.name);
    }
}

// Create and use a Person
const alice = new Person("Alice", 30);
console.log(alice.sayHello());
"""

    # Parse the JavaScript code
    result = parser.parse(js_code, "javascript")
    
    # Check if parsing was successful
    if "error" in result:
        logging.error(f"JavaScript parsing failed: {result['error']}")
        return False
    
    # Print AST structure
    print(f"JavaScript AST root type: {result['type']}")
    print(f"JavaScript AST node count: {len(result.get('children', []))} child nodes")
    
    return True

def test_java_parsing(parser):
    """Test parsing Java code."""
    print("\n===== TESTING JAVA PARSING =====")
    
    # Sample Java code
    java_code = """
public class Person {
    private String name;
    private int age;
    
    public Person(String name, int age) {
        this.name = name;
        this.age = age;
    }
    
    public String greet() {
        return "Hello, " + this.name + "!";
    }
    
    public static void main(String[] args) {
        Person person = new Person("Alice", 30);
        System.out.println(person.greet());
    }
}
"""

    # Parse the Java code
    result = parser.parse(java_code, "java")
    
    # Check if parsing was successful
    if "error" in result:
        logging.error(f"Java parsing failed: {result['error']}")
        return False
    
    # Print AST structure
    print(f"Java AST root type: {result['type']}")
    print(f"Java AST node count: {len(result.get('children', []))} child nodes")
    
    return True

def main():
    """Run tests for the BasicTreeSitterParser with multiple languages."""
    if not HAS_TREE_SITTER:
        logging.error("Tree-sitter is not available. Please install it with pip.")
        return 1

    # Initialize the parser
    parser = BasicTreeSitterParser()
    
    # Log supported languages
    supported_langs = parser.supported_languages()
    logging.info(f"Supported languages: {', '.join(supported_langs)}")
    
    # Test results
    python_ok = False
    js_ok = False
    java_ok = False
    
    # Run tests for each language if supported
    if "python" in supported_langs:
        python_ok = test_python_parsing(parser)
    else:
        logging.warning("Python language support is not available. Skipping test.")
    
    if "javascript" in supported_langs:
        js_ok = test_javascript_parsing(parser)
    else:
        logging.warning("JavaScript language support is not available. Skipping test.")
    
    if "java" in supported_langs:
        java_ok = test_java_parsing(parser)
    else:
        logging.warning("Java language support is not available. Skipping test.")
    
    # Print test summary
    print("\n===== TEST SUMMARY =====")
    print(f"Python parsing: {'SUCCESS' if python_ok else 'FAILED'}")
    print(f"JavaScript parsing: {'SUCCESS' if js_ok else 'FAILED'}")
    print(f"Java parsing: {'SUCCESS' if java_ok else 'FAILED'}")
    
    # Overall status
    if python_ok and js_ok and java_ok:
        print("\nAll language parsers are working correctly!")
        return 0
    else:
        print("\nSome language parsers failed. Check logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())