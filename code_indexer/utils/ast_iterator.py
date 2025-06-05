"""
AST Iterator Pattern

Implements the Iterator Pattern for memory-efficient traversal of Abstract Syntax Trees.
This allows processing large ASTs without loading the entire structure into memory.
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Iterator, Tuple, Generator, TypeVar, Generic

# Type variables for iteration
T = TypeVar('T')  # Node type


class ASTIterator(Generic[T], ABC):
    """
    Abstract base class for AST iterators.
    
    Implements the Iterator Pattern for memory-efficient traversal of ASTs.
    """
    
    @abstractmethod
    def __iter__(self) -> Iterator[T]:
        """Get iterator over AST nodes."""
        pass
    
    @abstractmethod
    def filter(self, predicate: callable) -> 'ASTIterator[T]':
        """
        Filter nodes based on a predicate.
        
        Args:
            predicate: Function that returns True for nodes to include
            
        Returns:
            Filtered iterator
        """
        pass


class FilteredASTIterator(ASTIterator[T]):
    """
    Iterator that filters nodes from another iterator.
    
    Applies a predicate function to each node from the source iterator.
    """
    
    def __init__(self, source_iterator: ASTIterator[T], predicate: callable):
        """
        Initialize filtered iterator.
        
        Args:
            source_iterator: Source iterator to filter from
            predicate: Function that returns True for nodes to include
        """
        self.source_iterator = source_iterator
        self.predicate = predicate
    
    def __iter__(self) -> Iterator[T]:
        """Get iterator over filtered nodes."""
        for node in self.source_iterator:
            if self.predicate(node):
                yield node
    
    def filter(self, predicate: callable) -> ASTIterator[T]:
        """
        Apply an additional filter.
        
        Args:
            predicate: Function that returns True for nodes to include
            
        Returns:
            Filtered iterator
        """
        # Combine predicates
        combined_predicate = lambda node: self.predicate(node) and predicate(node)
        return FilteredASTIterator(self.source_iterator, combined_predicate)


class DictASTIterator(ASTIterator[Dict[str, Any]]):
    """
    Iterator for dictionary-based AST representation.
    
    Traverses an AST represented as nested dictionaries.
    """
    
    def __init__(self, ast_data: Dict[str, Any], traverse_mode: str = "depth_first"):
        """
        Initialize dictionary AST iterator.
        
        Args:
            ast_data: AST data dictionary
            traverse_mode: Traversal mode ('depth_first' or 'breadth_first')
        """
        self.ast_data = ast_data
        self.traverse_mode = traverse_mode
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Get iterator over AST nodes."""
        if self.traverse_mode == "depth_first":
            yield from self._depth_first_traversal(self.ast_data)
        else:  # breadth_first
            yield from self._breadth_first_traversal(self.ast_data)
    
    def _depth_first_traversal(self, node: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """
        Perform depth-first traversal of AST.
        
        Args:
            node: Current AST node
            
        Yields:
            AST nodes in depth-first order
        """
        if not node or not isinstance(node, dict):
            return
        
        # Yield current node
        yield node
        
        # Determine AST format
        if "root" in node and isinstance(node["root"], dict):
            # Legacy format with separate root
            yield from self._depth_first_traversal(node["root"])
            return
            
        # Process children
        children = []
        
        # Direct children list (tree-sitter format)
        if "children" in node and isinstance(node["children"], list):
            children = node["children"]
        
        # Children dictionary (legacy format)
        elif "children" in node and isinstance(node["children"], dict):
            for child_list in node["children"].values():
                if isinstance(child_list, list):
                    children.extend(child_list)
                elif isinstance(child_list, dict):
                    children.append(child_list)
        
        # Attributes with nested nodes (legacy format)
        elif "attributes" in node and isinstance(node["attributes"], dict):
            for attr_value in node["attributes"].values():
                if isinstance(attr_value, dict) and "type" in attr_value:
                    children.append(attr_value)
                elif isinstance(attr_value, list):
                    for item in attr_value:
                        if isinstance(item, dict) and "type" in item:
                            children.append(item)
        
        # Recurse into children
        for child in children:
            yield from self._depth_first_traversal(child)
    
    def _breadth_first_traversal(self, node: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """
        Perform breadth-first traversal of AST.
        
        Args:
            node: Current AST node
            
        Yields:
            AST nodes in breadth-first order
        """
        if not node or not isinstance(node, dict):
            return
        
        # Initialize queue with root node
        queue = [node]
        
        # Handle legacy format with separate root
        if "root" in node and isinstance(node["root"], dict):
            queue = [node, node["root"]]
        
        # Process queue
        while queue:
            current = queue.pop(0)
            
            # Yield current node
            yield current
            
            # Process children
            children = []
            
            # Direct children list (tree-sitter format)
            if "children" in current and isinstance(current["children"], list):
                children = current["children"]
            
            # Children dictionary (legacy format)
            elif "children" in current and isinstance(current["children"], dict):
                for child_list in current["children"].values():
                    if isinstance(child_list, list):
                        children.extend(child_list)
                    elif isinstance(child_list, dict):
                        children.append(child_list)
            
            # Attributes with nested nodes (legacy format)
            elif "attributes" in current and isinstance(current["attributes"], dict):
                for attr_value in current["attributes"].values():
                    if isinstance(attr_value, dict) and "type" in attr_value:
                        children.append(attr_value)
                    elif isinstance(attr_value, list):
                        for item in attr_value:
                            if isinstance(item, dict) and "type" in item:
                                children.append(item)
            
            # Add children to queue
            queue.extend(children)
    
    def filter(self, predicate: callable) -> ASTIterator[Dict[str, Any]]:
        """
        Filter nodes based on a predicate.
        
        Args:
            predicate: Function that returns True for nodes to include
            
        Returns:
            Filtered iterator
        """
        return FilteredASTIterator(self, predicate)


class StreamingASTIterator(ASTIterator[Dict[str, Any]]):
    """
    Iterator for streaming AST processing.
    
    Reads and processes AST data in chunks without loading the entire AST into memory.
    """
    
    def __init__(self, file_path: str, chunk_size: int = 1000):
        """
        Initialize streaming AST iterator.
        
        Args:
            file_path: Path to the file containing the AST
            chunk_size: Number of lines to read at once
        """
        self.file_path = file_path
        self.chunk_size = chunk_size
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Get iterator over AST nodes from the file."""
        import json
        
        # Check if the file exists
        if not os.path.exists(self.file_path):
            return
        
        # Determine the format (JSON or custom)
        if self.file_path.endswith(".json"):
            # Read and parse JSON incrementally
            with open(self.file_path, 'r') as f:
                # Parse as JSON object
                try:
                    ast_data = json.load(f)
                    
                    # Use dictionary iterator for the loaded AST
                    dict_iterator = DictASTIterator(ast_data)
                    yield from dict_iterator
                except json.JSONDecodeError:
                    # Try line-by-line parsing (each line is a JSON object)
                    f.seek(0)
                    for line in f:
                        try:
                            node = json.loads(line.strip())
                            if isinstance(node, dict):
                                yield node
                        except json.JSONDecodeError:
                            continue
    
    def filter(self, predicate: callable) -> ASTIterator[Dict[str, Any]]:
        """
        Filter nodes based on a predicate.
        
        Args:
            predicate: Function that returns True for nodes to include
            
        Returns:
            Filtered iterator
        """
        return FilteredASTIterator(self, predicate)


class ASTIteratorFactory:
    """
    Factory for creating AST iterators.
    
    Implements the Factory Pattern to create appropriate iterator based on input.
    """
    
    @staticmethod
    def create_iterator(ast_data: Any, iterator_type: str = "dict", **kwargs) -> ASTIterator[Dict[str, Any]]:
        """
        Create an AST iterator.
        
        Args:
            ast_data: AST data (dictionary or file path)
            iterator_type: Type of iterator to create ('dict' or 'streaming')
            **kwargs: Additional parameters for the iterator
            
        Returns:
            AST iterator
        """
        if iterator_type == "dict" and isinstance(ast_data, dict):
            traverse_mode = kwargs.get("traverse_mode", "depth_first")
            return DictASTIterator(ast_data, traverse_mode)
        elif iterator_type == "streaming" and isinstance(ast_data, str):
            chunk_size = kwargs.get("chunk_size", 1000)
            return StreamingASTIterator(ast_data, chunk_size)
        else:
            # Default to dictionary iterator with empty dict
            return DictASTIterator({})


# Utility functions for common operations

def find_nodes_by_type(ast_iterator: ASTIterator[Dict[str, Any]], node_type: str) -> Iterator[Dict[str, Any]]:
    """
    Find all nodes of a specific type.
    
    Args:
        ast_iterator: AST iterator
        node_type: Type of nodes to find
        
    Returns:
        Iterator over matching nodes
    """
    predicate = lambda node: node.get("type") == node_type
    return ast_iterator.filter(predicate)


def find_nodes_by_name(ast_iterator: ASTIterator[Dict[str, Any]], name: str) -> Iterator[Dict[str, Any]]:
    """
    Find all nodes with a specific name.
    
    Args:
        ast_iterator: AST iterator
        name: Name to search for
        
    Returns:
        Iterator over matching nodes
    """
    def has_name(node):
        # Check attributes dictionary
        if "attributes" in node and isinstance(node["attributes"], dict):
            if node["attributes"].get("name") == name or node["attributes"].get("id") == name:
                return True
        
        # Check direct text field (tree-sitter format)
        if "text" in node and node["text"] == name:
            return True
        
        return False
    
    return ast_iterator.filter(has_name)


def get_functions(ast_iterator: ASTIterator[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    Get all function nodes.
    
    Args:
        ast_iterator: AST iterator
        
    Returns:
        Iterator over function nodes
    """
    # Expanded function types to support more languages
    function_types = [
        # Python
        "FunctionDef", "function_definition", "Function", 
        # JavaScript/TypeScript
        "MethodDefinition", "method_definition", "function_declaration", 
        "method_declaration", "arrow_function", "generator_function_declaration",
        # Java
        "method_declaration", "constructor_declaration",
        # C/C++
        "function_definition", "function_declarator", "method_definition",
        # Go
        "function_declaration", "method_declaration",
        # Ruby
        "method", "singleton_method", "method_definition",
        # Generic
        "function", "method"
    ]
    
    def is_function(node):
        return node.get("type") in function_types
    
    return ast_iterator.filter(is_function)


def get_calls(ast_iterator: ASTIterator[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    Get all call nodes.
    
    Args:
        ast_iterator: AST iterator
        
    Returns:
        Iterator over call nodes
    """
    call_types = ["Call", "call"]
    
    def is_call(node):
        return node.get("type") in call_types
    
    return ast_iterator.filter(is_call)


def get_imports(ast_iterator: ASTIterator[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    Get all import nodes.
    
    Args:
        ast_iterator: AST iterator
        
    Returns:
        Iterator over import nodes
    """
    import_types = ["Import", "import_statement", "ImportFrom", "import_from_statement"]
    
    def is_import(node):
        return node.get("type") in import_types
    
    return ast_iterator.filter(is_import)