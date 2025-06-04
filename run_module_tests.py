#!/usr/bin/env python3
"""
Comprehensive test script to verify functionality of key components in each module.
"""

import os
import sys
import unittest
import logging
import importlib
import inspect
from typing import List, Dict, Any, Callable, Optional, Tuple
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("module_tests")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add mocks directory to path
mocks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests', 'mocks')
sys.path.insert(0, mocks_path)

# Define modules to test
MODULES_TO_TEST = [
    "code_indexer.tools.ast_extractor",
    "code_indexer.tools.tree_sitter_parser",
    "code_indexer.tools.git_tool",
    "code_indexer.tools.neo4j_tool",
    "code_indexer.tools.vector_store_interface",
    "code_indexer.tools.vector_store_factory",
    "code_indexer.ingestion.direct.ast_extractor",
    "code_indexer.ingestion.direct.git_ingestion",
    "code_indexer.ingestion.direct.graph_builder",
    "code_indexer.ingestion.pipeline",
    "code_indexer.utils.ast_utils",
    "code_indexer.utils.repo_utils",
    "code_indexer.utils.vector_store_utils",
]

class ModuleTester:
    """Tests the basic functionality of modules by importing and checking classes."""
    
    def __init__(self):
        self.results = {}
        self.class_counts = {}
        self.function_counts = {}
        self.errors = {}
    
    def test_module_import(self, module_name: str) -> bool:
        """Test that a module can be imported."""
        try:
            module = importlib.import_module(module_name)
            return True
        except Exception as e:
            logger.error(f"Error importing {module_name}: {e}")
            self.errors[module_name] = str(e)
            return False
    
    def analyze_module(self, module_name: str) -> Dict[str, Any]:
        """Analyze a module to get classes and functions."""
        if not self.test_module_import(module_name):
            return None
        
        module = importlib.import_module(module_name)
        
        # Get all classes and functions in the module
        classes = []
        functions = []
        
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and obj.__module__ == module_name:
                classes.append(name)
            elif inspect.isfunction(obj) and obj.__module__ == module_name:
                functions.append(name)
        
        self.class_counts[module_name] = len(classes)
        self.function_counts[module_name] = len(functions)
        
        return {
            "module": module,
            "classes": classes,
            "functions": functions
        }
    
    def test_all_modules(self) -> Dict[str, Dict[str, Any]]:
        """Test all modules in the MODULES_TO_TEST list."""
        for module_name in MODULES_TO_TEST:
            logger.info(f"Testing module: {module_name}")
            result = self.analyze_module(module_name)
            self.results[module_name] = result
            
            if result:
                logger.info(f"✓ Module {module_name} imported successfully")
                logger.info(f"  - Found {len(result['classes'])} classes: {', '.join(result['classes'])}")
                logger.info(f"  - Found {len(result['functions'])} functions")
            else:
                logger.error(f"✗ Module {module_name} import failed")
        
        return self.results
    
    def test_instantiate_classes(self) -> Dict[str, Dict[str, bool]]:
        """Test instantiating classes with default constructors where possible."""
        instantiation_results = {}
        
        for module_name, result in self.results.items():
            if not result:
                continue
                
            module = result["module"]
            class_results = {}
            
            for class_name in result["classes"]:
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
                    except (TypeError, ValueError) as e:
                        logger.warning(f"  ⚠ Cannot instantiate {class_name}: {e}")
                        logger.warning(f"    Constructor params: {constructor_params}")
                    
                    class_results[class_name] = {
                        "can_instantiate": can_instantiate,
                        "constructor_params": constructor_params
                    }
                    
                except Exception as e:
                    logger.error(f"  ✗ Error analyzing {class_name}: {e}")
                    class_results[class_name] = {"error": str(e)}
            
            instantiation_results[module_name] = class_results
        
        return instantiation_results
    
    def generate_report(self) -> str:
        """Generate a report of the test results."""
        report = []
        report.append("# Module Test Report\n")
        
        report.append("## Summary\n")
        total_modules = len(MODULES_TO_TEST)
        successful_imports = sum(1 for r in self.results.values() if r is not None)
        report.append(f"- Total modules tested: {total_modules}")
        report.append(f"- Successful imports: {successful_imports}")
        report.append(f"- Failed imports: {total_modules - successful_imports}")
        
        total_classes = sum(self.class_counts.values())
        total_functions = sum(self.function_counts.values())
        report.append(f"- Total classes found: {total_classes}")
        report.append(f"- Total functions found: {total_functions}\n")
        
        report.append("## Module Details\n")
        for module_name in MODULES_TO_TEST:
            report.append(f"### {module_name}\n")
            
            if module_name in self.errors:
                report.append(f"❌ **Import Failed**: {self.errors[module_name]}\n")
                continue
            
            result = self.results[module_name]
            report.append(f"✅ **Import Successful**\n")
            
            if result:
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
    """Run the module tests."""
    try:
        logger.info("Starting module tests...")
        
        tester = ModuleTester()
        tester.test_all_modules()
        tester.test_instantiate_classes()
        
        # Generate report
        report = tester.generate_report()
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "module_test_report.md")
        with open(report_path, "w") as f:
            f.write(report)
        
        logger.info(f"Test report written to {report_path}")
        logger.info("Module tests completed!")
        return 0
        
    except Exception as e:
        logger.error(f"Error running module tests: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())