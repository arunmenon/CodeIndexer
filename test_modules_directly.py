#!/usr/bin/env python3
"""
Direct module testing script that uses file paths instead of imports.
"""

import os
import sys
import logging
import inspect
import importlib.util
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_module_tests")

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Define modules to test
MODULES_TO_TEST = [
    "code_indexer/tools/ast_extractor.py",
    "code_indexer/tools/tree_sitter_parser.py",
    "code_indexer/tools/git_tool.py",
    "code_indexer/tools/neo4j_tool.py",
    "code_indexer/tools/vector_store_interface.py",
    "code_indexer/tools/vector_store_factory.py",
    "code_indexer/ingestion/direct/ast_extractor.py",
    "code_indexer/ingestion/direct/git_ingestion.py",
    "code_indexer/ingestion/direct/graph_builder.py",
    "code_indexer/ingestion/pipeline.py",
    "code_indexer/utils/ast_utils.py",
    "code_indexer/utils/repo_utils.py",
    "code_indexer/utils/vector_store_utils.py",
]

def load_module_from_file(file_path: str) -> Optional[Any]:
    """Load a module directly from a file path."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return None
    
    try:
        module_name = file_path.replace('/', '.').replace('.py', '')
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.error(f"Error loading module from {file_path}: {e}")
        return None

def analyze_module_file(file_path: str) -> Dict[str, Any]:
    """Analyze a module file to extract classes and functions."""
    module = load_module_from_file(file_path)
    if not module:
        return None
    
    # Get all classes and functions in the module
    classes = []
    functions = []
    
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module.__name__:
            classes.append(name)
        elif inspect.isfunction(obj) and obj.__module__ == module.__name__:
            functions.append(name)
    
    return {
        "module": module,
        "classes": classes,
        "functions": functions,
        "file_path": file_path
    }

def test_module_instantiation(module_info: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Test instantiating classes with default constructors where possible."""
    if not module_info:
        return {}
    
    module = module_info["module"]
    class_results = {}
    
    for class_name in module_info["classes"]:
        try:
            # Get the class object
            class_obj = getattr(module, class_name)
            
            # Check if we can instantiate it
            can_instantiate = False
            constructor_params = []
            
            # Get constructor parameters
            try:
                signature = inspect.signature(class_obj.__init__)
                params = list(signature.parameters.values())[1:]  # Skip 'self'
                constructor_params = [p.name for p in params]
                
                # Skip classes with required parameters for now
                required_params = [p for p in params if p.default == inspect.Parameter.empty]
                if not required_params:
                    # Try to instantiate with default values
                    instance = class_obj()
                    can_instantiate = True
                    logger.info(f"  ✓ Class {class_name} instantiated successfully")
                else:
                    logger.info(f"  ⚠ Class {class_name} requires parameters: {', '.join(p.name for p in required_params)}")
            except (TypeError, ValueError) as e:
                logger.warning(f"  ⚠ Cannot analyze constructor for {class_name}: {e}")
            
            class_results[class_name] = {
                "can_instantiate": can_instantiate,
                "constructor_params": constructor_params
            }
            
        except Exception as e:
            logger.error(f"  ✗ Error analyzing {class_name}: {e}")
            class_results[class_name] = {"error": str(e)}
    
    return class_results

def generate_report(results: Dict[str, Dict[str, Any]]) -> str:
    """Generate a report of the test results."""
    report = []
    report.append("# Module Test Report (Direct File Analysis)\n")
    
    report.append("## Summary\n")
    total_modules = len(MODULES_TO_TEST)
    successful_loads = sum(1 for r in results.values() if r is not None)
    report.append(f"- Total modules tested: {total_modules}")
    report.append(f"- Successfully loaded: {successful_loads}")
    report.append(f"- Failed to load: {total_modules - successful_loads}")
    
    total_classes = sum(len(r["classes"]) for r in results.values() if r is not None)
    total_functions = sum(len(r["functions"]) for r in results.values() if r is not None)
    report.append(f"- Total classes found: {total_classes}")
    report.append(f"- Total functions found: {total_functions}\n")
    
    report.append("## Module Details\n")
    for file_path in MODULES_TO_TEST:
        report.append(f"### {file_path}\n")
        
        if file_path not in results or results[file_path] is None:
            report.append(f"❌ **Load Failed**\n")
            continue
        
        result = results[file_path]
        report.append(f"✅ **Load Successful**\n")
        
        # Classes
        report.append(f"**Classes ({len(result['classes'])}):**\n")
        if result['classes']:
            for class_name in result['classes']:
                report.append(f"- `{class_name}`")
        else:
            report.append("- *No classes found*")
        report.append("")
        
        # Functions
        report.append(f"**Functions ({len(result['functions'])}):**\n")
        if result['functions']:
            for func_name in result['functions']:
                report.append(f"- `{func_name}`")
        else:
            report.append("- *No functions found*")
        report.append("")
    
    return "\n".join(report)

def main():
    """Run direct module file tests."""
    try:
        logger.info("Starting direct module file tests...")
        
        # Process all modules
        results = {}
        for file_path in MODULES_TO_TEST:
            logger.info(f"Testing file: {file_path}")
            full_path = os.path.join(project_root, file_path)
            
            if not os.path.exists(full_path):
                logger.error(f"File not found: {full_path}")
                results[file_path] = None
                continue
                
            result = analyze_module_file(full_path)
            results[file_path] = result
            
            if result:
                logger.info(f"✓ Module {file_path} loaded successfully")
                logger.info(f"  - Found {len(result['classes'])} classes: {', '.join(result['classes'])}")
                logger.info(f"  - Found {len(result['functions'])} functions")
                
                # Test class instantiation
                test_module_instantiation(result)
            else:
                logger.error(f"✗ Module {file_path} load failed")
        
        # Generate report
        report = generate_report(results)
        report_path = os.path.join(project_root, "direct_module_test_report.md")
        with open(report_path, "w") as f:
            f.write(report)
        
        logger.info(f"Test report written to {report_path}")
        logger.info("Direct module file tests completed!")
        return 0
        
    except Exception as e:
        logger.error(f"Error running direct module file tests: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())