"""
AST Composite Pattern

Provides a Composite Pattern implementation for working with Abstract Syntax Trees
in a more object-oriented way, allowing for uniform handling of nodes and operations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable, Iterator, TypeVar, Generic

# Type variables for visitor pattern
T = TypeVar('T')  # Return type from visitors


class ASTNode(ABC):
    """
    Abstract base class for AST nodes in the Composite Pattern.
    
    Provides a common interface for leaf nodes and composite nodes in the AST.
    """
    
    def __init__(self, data: Dict[str, Any]):
        """
        Initialize the AST node.
        
        Args:
            data: Node data dictionary
        """
        self.data = data
        self.parent = None
    
    @property
    def node_type(self) -> str:
        """Get the type of this node."""
        return self.data.get("type", "unknown")
    
    @property
    def children(self) -> List['ASTNode']:
        """Get the child nodes of this node."""
        return []
    
    @abstractmethod
    def accept(self, visitor: Callable[['ASTNode'], T]) -> T:
        """
        Accept a visitor that processes this node.
        
        Args:
            visitor: Visitor function or object
            
        Returns:
            Result of the visitor's processing
        """
        pass
    
    def add_child(self, child: 'ASTNode') -> None:
        """
        Add a child node.
        
        Args:
            child: Child node to add
        """
        pass
    
    def remove_child(self, child: 'ASTNode') -> None:
        """
        Remove a child node.
        
        Args:
            child: Child node to remove
        """
        pass
    
    def find_first(self, predicate: Callable[['ASTNode'], bool]) -> Optional['ASTNode']:
        """
        Find the first node that matches the predicate.
        
        Args:
            predicate: Function that returns True for matching nodes
            
        Returns:
            First matching node or None
        """
        if predicate(self):
            return self
        return None
    
    def find_all(self, predicate: Callable[['ASTNode'], bool]) -> List['ASTNode']:
        """
        Find all nodes that match the predicate.
        
        Args:
            predicate: Function that returns True for matching nodes
            
        Returns:
            List of matching nodes
        """
        return [self] if predicate(self) else []
    
    def get_path(self) -> List['ASTNode']:
        """
        Get the path from the root to this node.
        
        Returns:
            List of nodes from root to this node
        """
        if self.parent is None:
            return [self]
        else:
            return self.parent.get_path() + [self]
    
    def get_position(self) -> Dict[str, Any]:
        """
        Get the position of this node in the source code.
        
        Returns:
            Dictionary with position information
        """
        # Check for tree-sitter format first
        if "start_point" in self.data and "end_point" in self.data:
            start_point = self.data["start_point"]
            end_point = self.data["end_point"]
            
            # Handle different position formats
            if isinstance(start_point, dict):
                return {
                    "start_line": start_point.get("row", 0),
                    "start_column": start_point.get("column", 0),
                    "end_line": end_point.get("row", 0),
                    "end_column": end_point.get("column", 0)
                }
            else:
                # Tuple format
                return {
                    "start_line": start_point[0] if len(start_point) > 0 else 0,
                    "start_column": start_point[1] if len(start_point) > 1 else 0,
                    "end_line": end_point[0] if len(end_point) > 0 else 0,
                    "end_column": end_point[1] if len(end_point) > 1 else 0
                }
        
        # Legacy format
        elif "start_position" in self.data and "end_position" in self.data:
            start_pos = self.data["start_position"]
            end_pos = self.data["end_position"]
            
            return {
                "start_line": start_pos.get("row", 0),
                "start_column": start_pos.get("column", 0),
                "end_line": end_pos.get("row", 0),
                "end_column": end_pos.get("column", 0)
            }
        
        # No position information
        return {
            "start_line": 0,
            "start_column": 0,
            "end_line": 0,
            "end_column": 0
        }
    
    def get_text(self) -> str:
        """
        Get the text content of this node.
        
        Returns:
            Text content or empty string
        """
        return self.data.get("text", "")
    
    def get_attributes(self) -> Dict[str, Any]:
        """
        Get the attributes of this node.
        
        Returns:
            Dictionary of attributes
        """
        return self.data.get("attributes", {})
    
    def __str__(self) -> str:
        """Get string representation."""
        return f"{self.node_type} at {self.get_position()}"


class LeafNode(ASTNode):
    """
    Leaf node in the AST composite hierarchy.
    
    Represents terminal nodes with no children.
    """
    
    def accept(self, visitor: Callable[[ASTNode], T]) -> T:
        """
        Accept a visitor.
        
        Args:
            visitor: Visitor function or object
            
        Returns:
            Result of visitor's processing
        """
        return visitor(self)


class CompositeNode(ASTNode):
    """
    Composite node in the AST composite hierarchy.
    
    Represents non-terminal nodes with children.
    """
    
    def __init__(self, data: Dict[str, Any]):
        """
        Initialize the composite node.
        
        Args:
            data: Node data dictionary
        """
        super().__init__(data)
        self._children = []
        self._initialize_children()
    
    def _initialize_children(self) -> None:
        """Initialize children from the data dictionary."""
        # Handle different AST formats
        children_data = []
        
        # Tree-sitter format with direct children array
        if "children" in self.data and isinstance(self.data["children"], list):
            children_data = self.data["children"]
        
        # Legacy format with nested children dictionary
        elif "children" in self.data and isinstance(self.data["children"], dict):
            for child_list in self.data["children"].values():
                if isinstance(child_list, list):
                    children_data.extend(child_list)
                elif isinstance(child_list, dict):
                    children_data.append(child_list)
        
        # Create child nodes
        for child_data in children_data:
            if isinstance(child_data, dict):
                # Determine if child is a leaf or composite
                if "children" in child_data:
                    if isinstance(child_data["children"], list) and child_data["children"]:
                        child_node = CompositeNode(child_data)
                    elif isinstance(child_data["children"], dict) and child_data["children"]:
                        child_node = CompositeNode(child_data)
                    else:
                        child_node = LeafNode(child_data)
                else:
                    child_node = LeafNode(child_data)
                
                # Add child
                self.add_child(child_node)
    
    @property
    def children(self) -> List[ASTNode]:
        """Get the child nodes."""
        return self._children
    
    def add_child(self, child: ASTNode) -> None:
        """
        Add a child node.
        
        Args:
            child: Child node to add
        """
        self._children.append(child)
        child.parent = self
    
    def remove_child(self, child: ASTNode) -> None:
        """
        Remove a child node.
        
        Args:
            child: Child node to remove
        """
        if child in self._children:
            self._children.remove(child)
            child.parent = None
    
    def accept(self, visitor: Callable[[ASTNode], T]) -> T:
        """
        Accept a visitor and visit all children.
        
        Args:
            visitor: Visitor function or object
            
        Returns:
            Result of visitor's processing
        """
        result = visitor(self)
        
        # Process children
        for child in self.children:
            child.accept(visitor)
        
        return result
    
    def find_first(self, predicate: Callable[[ASTNode], bool]) -> Optional[ASTNode]:
        """
        Find the first node that matches the predicate.
        
        Args:
            predicate: Function that returns True for matching nodes
            
        Returns:
            First matching node or None
        """
        # Check self first
        if predicate(self):
            return self
        
        # Check children
        for child in self.children:
            result = child.find_first(predicate)
            if result:
                return result
        
        return None
    
    def find_all(self, predicate: Callable[[ASTNode], bool]) -> List[ASTNode]:
        """
        Find all nodes that match the predicate.
        
        Args:
            predicate: Function that returns True for matching nodes
            
        Returns:
            List of matching nodes
        """
        results = []
        
        # Check self
        if predicate(self):
            results.append(self)
        
        # Check children
        for child in self.children:
            results.extend(child.find_all(predicate))
        
        return results


class ASTComposite:
    """
    Factory class for creating AST composite structures.
    
    Provides methods for creating and working with AST nodes in the Composite Pattern.
    """
    
    @staticmethod
    def create_from_dict(ast_data: Dict[str, Any]) -> ASTNode:
        """
        Create an AST composite structure from a dictionary.
        
        Args:
            ast_data: AST data dictionary
            
        Returns:
            Root node of the AST
        """
        # Determine the root node
        root_data = ast_data
        
        # Handle different AST formats
        if "root" in ast_data:
            # Legacy format with separate root node
            root_data = ast_data["root"]
        elif "type" in ast_data and ("children" in ast_data or "attributes" in ast_data):
            # Tree-sitter format where the AST itself is the root
            root_data = ast_data
        
        # Create the root node
        if isinstance(root_data, dict):
            # Check if it's a composite or leaf
            has_children = (
                "children" in root_data and 
                (isinstance(root_data["children"], list) or isinstance(root_data["children"], dict))
            )
            
            if has_children:
                return CompositeNode(root_data)
            else:
                return LeafNode(root_data)
        else:
            # Invalid root data
            raise ValueError("Invalid AST data: root must be a dictionary")
    
    @staticmethod
    def find_nodes_by_type(root: ASTNode, node_type: str) -> List[ASTNode]:
        """
        Find all nodes of a specific type.
        
        Args:
            root: Root node to start search from
            node_type: Type of nodes to find
            
        Returns:
            List of matching nodes
        """
        return root.find_all(lambda node: node.node_type == node_type)
    
    @staticmethod
    def find_nodes_with_text(root: ASTNode, text: str) -> List[ASTNode]:
        """
        Find all nodes with specific text content.
        
        Args:
            root: Root node to start search from
            text: Text to search for
            
        Returns:
            List of matching nodes
        """
        return root.find_all(lambda node: text in node.get_text())
    
    @staticmethod
    def get_functions(root: ASTNode) -> List[ASTNode]:
        """
        Get all function nodes in the AST.
        
        Args:
            root: Root node to start search from
            
        Returns:
            List of function nodes
        """
        # Handle different AST formats and function node types
        function_types = ["FunctionDef", "function_definition", "Function"]
        
        result = []
        for func_type in function_types:
            result.extend(ASTComposite.find_nodes_by_type(root, func_type))
        
        return result
    
    @staticmethod
    def get_classes(root: ASTNode) -> List[ASTNode]:
        """
        Get all class nodes in the AST.
        
        Args:
            root: Root node to start search from
            
        Returns:
            List of class nodes
        """
        # Handle different AST formats and class node types
        class_types = ["ClassDef", "class_definition", "Class"]
        
        result = []
        for class_type in class_types:
            result.extend(ASTComposite.find_nodes_by_type(root, class_type))
        
        return result
    
    @staticmethod
    def get_calls(root: ASTNode) -> List[ASTNode]:
        """
        Get all call nodes in the AST.
        
        Args:
            root: Root node to start search from
            
        Returns:
            List of call nodes
        """
        # Handle different AST formats and call node types
        call_types = ["Call", "call"]
        
        result = []
        for call_type in call_types:
            result.extend(ASTComposite.find_nodes_by_type(root, call_type))
        
        return result
    
    @staticmethod
    def get_imports(root: ASTNode) -> List[ASTNode]:
        """
        Get all import nodes in the AST.
        
        Args:
            root: Root node to start search from
            
        Returns:
            List of import nodes
        """
        # Handle different AST formats and import node types
        import_types = ["Import", "import_statement", "ImportFrom", "import_from_statement"]
        
        result = []
        for import_type in import_types:
            result.extend(ASTComposite.find_nodes_by_type(root, import_type))
        
        return result