"""
AST Visitor Pattern

Implements the Visitor Pattern for traversing and processing AST nodes,
working with the AST Composite Pattern.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable, Generic, TypeVar

from code_indexer.utils.ast_composite import ASTNode, CompositeNode, LeafNode

# Type variables for return types
T = TypeVar('T')  # Return type for visitor methods
R = TypeVar('R')  # Accumulator type for visitors


class ASTVisitor(Generic[T, R], ABC):
    """
    Abstract base class for AST visitors.
    
    Implements the Visitor Pattern for processing AST nodes with type-specific methods.
    """
    
    def __init__(self):
        """Initialize the AST visitor."""
        # Initialize accumulator for collecting results
        self.accumulator = None
    
    @abstractmethod
    def visit(self, node: ASTNode) -> T:
        """
        Visit an AST node.
        
        This is the entry point for the visitor pattern. It dispatches to type-specific
        visit methods based on the node type.
        
        Args:
            node: AST node to visit
            
        Returns:
            Result of visiting the node
        """
        pass
    
    def visit_node(self, node: ASTNode) -> T:
        """
        Default visit method for any node.
        
        Override this for common processing across all node types.
        
        Args:
            node: AST node to visit
            
        Returns:
            Result of visiting the node
        """
        return None
    
    def get_result(self) -> R:
        """
        Get the accumulated result.
        
        Returns:
            Accumulated result
        """
        return self.accumulator


class NodeTypeVisitor(ASTVisitor[None, Dict[str, int]]):
    """
    Visitor that counts nodes by type.
    
    Useful for analyzing the structure of an AST.
    """
    
    def __init__(self):
        """Initialize the node type visitor."""
        super().__init__()
        self.accumulator = {}
    
    def visit(self, node: ASTNode) -> None:
        """
        Visit an AST node and count its type.
        
        Args:
            node: AST node to visit
        """
        node_type = node.node_type
        
        # Increment counter for this node type
        if node_type in self.accumulator:
            self.accumulator[node_type] += 1
        else:
            self.accumulator[node_type] = 1
        
        # Visit children
        if isinstance(node, CompositeNode):
            for child in node.children:
                self.visit(child)


class CallVisitor(ASTVisitor[None, List[Dict[str, Any]]]):
    """
    Visitor that collects information about function calls.
    
    Useful for analyzing function calls in code.
    """
    
    def __init__(self):
        """Initialize the call visitor."""
        super().__init__()
        self.accumulator = []
    
    def visit(self, node: ASTNode) -> None:
        """
        Visit an AST node and collect call information.
        
        Args:
            node: AST node to visit
        """
        # Check if this is a call node
        if node.node_type in ["Call", "call"]:
            # Extract call information
            call_info = self._extract_call_info(node)
            if call_info:
                self.accumulator.append(call_info)
        
        # Visit children
        if isinstance(node, CompositeNode):
            for child in node.children:
                self.visit(child)
    
    def _extract_call_info(self, node: ASTNode) -> Optional[Dict[str, Any]]:
        """
        Extract information about a function call.
        
        Args:
            node: Call node
            
        Returns:
            Dictionary with call information or None
        """
        position = node.get_position()
        
        # Handle tree-sitter format
        if node.node_type == "call" and node.children:
            # First child is usually the function name
            func_node = node.children[0]
            
            # Check if it's a direct call or attribute call
            if func_node.node_type == "identifier":
                return {
                    "name": func_node.get_text(),
                    "is_attribute": False,
                    "position": position
                }
            elif func_node.node_type == "attribute":
                # Get attribute pieces
                if len(func_node.children) >= 3:
                    obj_node = func_node.children[0]
                    attr_node = func_node.children[2]
                    
                    return {
                        "name": attr_node.get_text(),
                        "object": obj_node.get_text(),
                        "is_attribute": True,
                        "position": position
                    }
        
        # Handle legacy format
        elif node.node_type == "Call":
            attrs = node.get_attributes()
            if "func" in attrs:
                func = attrs["func"]
                
                if func.get("type") == "Name":
                    return {
                        "name": func.get("attributes", {}).get("id", ""),
                        "is_attribute": False,
                        "position": position
                    }
                elif func.get("type") == "Attribute":
                    func_attrs = func.get("attributes", {})
                    value = func_attrs.get("value", {})
                    
                    return {
                        "name": func_attrs.get("attr", ""),
                        "object": value.get("attributes", {}).get("id", ""),
                        "is_attribute": True,
                        "position": position
                    }
        
        return None


class FunctionVisitor(ASTVisitor[None, List[Dict[str, Any]]]):
    """
    Visitor that collects information about function definitions.
    
    Useful for analyzing function definitions in code.
    """
    
    def __init__(self):
        """Initialize the function visitor."""
        super().__init__()
        self.accumulator = []
        self.current_class = None
    
    def visit(self, node: ASTNode) -> None:
        """
        Visit an AST node and collect function information.
        
        Args:
            node: AST node to visit
        """
        # Check for class definition
        if node.node_type in ["ClassDef", "class_definition", "Class"]:
            # Save previous class context
            prev_class = self.current_class
            
            # Set current class
            self.current_class = self._extract_class_info(node)
            
            # Visit children
            if isinstance(node, CompositeNode):
                for child in node.children:
                    self.visit(child)
            
            # Restore previous class context
            self.current_class = prev_class
            
            # Skip further processing for this node
            return
        
        # Check if this is a function node
        if node.node_type in ["FunctionDef", "function_definition", "Function"]:
            # Extract function information
            func_info = self._extract_function_info(node)
            
            # Add class information if inside a class
            if self.current_class:
                func_info["class_name"] = self.current_class.get("name", "")
                func_info["class_id"] = self.current_class.get("id", "")
                func_info["is_method"] = True
            
            self.accumulator.append(func_info)
        
        # Visit children
        if isinstance(node, CompositeNode):
            for child in node.children:
                self.visit(child)
    
    def _extract_function_info(self, node: ASTNode) -> Dict[str, Any]:
        """
        Extract information about a function definition.
        
        Args:
            node: Function node
            
        Returns:
            Dictionary with function information
        """
        position = node.get_position()
        
        # Get function name
        name = ""
        
        # Tree-sitter format
        if node.node_type in ["function_definition", "Function"]:
            # Look for identifier child
            for child in node.children:
                if child.node_type == "identifier":
                    name = child.get_text()
                    break
        
        # Legacy format
        elif node.node_type == "FunctionDef":
            attrs = node.get_attributes()
            name = attrs.get("name", "")
        
        # Create function info
        return {
            "name": name,
            "type": node.node_type,
            "position": position,
            "is_method": False  # Will be updated by visit method if inside a class
        }
    
    def _extract_class_info(self, node: ASTNode) -> Dict[str, Any]:
        """
        Extract information about a class definition.
        
        Args:
            node: Class node
            
        Returns:
            Dictionary with class information
        """
        position = node.get_position()
        
        # Get class name
        name = ""
        
        # Tree-sitter format
        if node.node_type in ["class_definition", "Class"]:
            # Look for identifier child
            for child in node.children:
                if child.node_type == "identifier":
                    name = child.get_text()
                    break
        
        # Legacy format
        elif node.node_type == "ClassDef":
            attrs = node.get_attributes()
            name = attrs.get("name", "")
        
        # Generate ID
        class_id = f"class_{name}_{position['start_line']}"
        
        # Create class info
        return {
            "id": class_id,
            "name": name,
            "type": node.node_type,
            "position": position
        }


class ImportVisitor(ASTVisitor[None, List[Dict[str, Any]]]):
    """
    Visitor that collects information about imports.
    
    Useful for analyzing import statements in code.
    """
    
    def __init__(self):
        """Initialize the import visitor."""
        super().__init__()
        self.accumulator = []
    
    def visit(self, node: ASTNode) -> None:
        """
        Visit an AST node and collect import information.
        
        Args:
            node: AST node to visit
        """
        # Check if this is an import node
        if node.node_type in ["Import", "import_statement"]:
            # Extract import information
            imports = self._extract_import_info(node, False)
            self.accumulator.extend(imports)
        elif node.node_type in ["ImportFrom", "import_from_statement"]:
            # Extract import from information
            imports = self._extract_import_info(node, True)
            self.accumulator.extend(imports)
        
        # Visit children
        if isinstance(node, CompositeNode):
            for child in node.children:
                self.visit(child)
    
    def _extract_import_info(self, node: ASTNode, is_from_import: bool) -> List[Dict[str, Any]]:
        """
        Extract information about import statements.
        
        Args:
            node: Import node
            is_from_import: Whether this is an import-from statement
            
        Returns:
            List of dictionaries with import information
        """
        position = node.get_position()
        imports = []
        
        # Legacy format
        if node.node_type in ["Import", "ImportFrom"]:
            attrs = node.get_attributes()
            
            if "names" in attrs:
                module = attrs.get("module", "") if is_from_import else ""
                
                for alias in attrs["names"]:
                    imports.append({
                        "name": alias.get("name", ""),
                        "alias": alias.get("asname", ""),
                        "module": module,
                        "is_from_import": is_from_import,
                        "position": position
                    })
        
        # Tree-sitter format
        elif node.node_type in ["import_statement", "import_from_statement"]:
            module = ""
            
            # For import-from, get the module name
            if is_from_import:
                # Look for the module name in dotted_name
                for child in node.children:
                    if child.node_type == "dotted_name":
                        parts = []
                        for part_node in child.children:
                            if part_node.node_type == "identifier":
                                parts.append(part_node.get_text())
                        module = ".".join(parts)
                        break
            
            # Get imported names
            import_items = []
            
            # For import-from, look for import_items block
            if is_from_import:
                for child in node.children:
                    if child.node_type == "import_items":
                        for item in child.children:
                            if item.node_type == "dotted_name":
                                name = ""
                                for part_node in item.children:
                                    if part_node.node_type == "identifier":
                                        name = part_node.get_text()
                                        break
                                if name:
                                    import_items.append({"name": name, "alias": ""})
            # For regular import, look for dotted_name
            else:
                for child in node.children:
                    if child.node_type == "dotted_name":
                        name = ""
                        for part_node in child.children:
                            if part_node.node_type == "identifier":
                                name = part_node.get_text()
                                break
                        if name:
                            import_items.append({"name": name, "alias": ""})
            
            # Create import information
            for item in import_items:
                imports.append({
                    "name": item["name"],
                    "alias": item["alias"],
                    "module": module,
                    "is_from_import": is_from_import,
                    "position": position
                })
        
        return imports