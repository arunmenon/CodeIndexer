#!/usr/bin/env python
"""Find the location of key ADK classes in the installed google-adk package."""

import importlib
import inspect
import pkgutil
import sys

def find_class_in_module(module_name, class_name):
    """Find a class in a module and its submodules."""
    try:
        module = importlib.import_module(module_name)
        # Check if the class is directly in this module
        if hasattr(module, class_name):
            return f"{module_name}.{class_name}"
        
        # Check submodules
        for _, name, is_pkg in pkgutil.iter_modules(module.__path__, module.__name__ + '.'):
            result = find_class_in_module(name, class_name)
            if result:
                return result
    except (ImportError, AttributeError):
        pass
    return None

def main():
    """Find key ADK classes."""
    classes_to_find = [
        'Agent', 
        'AgentContext', 
        'HandlerResponse',
        'ToolContext', 
        'ToolResponse', 
        'ToolStatus',
        'BaseTool'
    ]
    
    print("Searching for ADK classes...")
    for class_name in classes_to_find:
        path = find_class_in_module('google.adk', class_name)
        print(f"{class_name}: {path}")

if __name__ == "__main__":
    main()