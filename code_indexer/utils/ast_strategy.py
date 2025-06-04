"""
AST Processing Strategy Pattern

Implements the Strategy Pattern for different AST processing approaches,
allowing runtime selection of the most appropriate processing strategy
based on AST characteristics and performance requirements.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union

from code_indexer.utils.ast_iterator import (
    ASTIterator, DictASTIterator, StreamingASTIterator, ASTIteratorFactory,
    find_nodes_by_type, get_functions, get_calls, get_imports
)
from code_indexer.utils.ast_composite import ASTComposite, ASTNode, CompositeNode, LeafNode
from code_indexer.utils.ast_visitor import ASTVisitor, CallVisitor, FunctionVisitor, ImportVisitor


class ASTProcessingStrategy(ABC):
    """
    Abstract base class for AST processing strategies.
    
    Defines the interface for all concrete processing strategies,
    implementing the Strategy Pattern.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the processing strategy.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def process_ast(self, ast_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AST using this strategy.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            Dictionary with processing results
        """
        pass
    
    @classmethod
    def can_process(cls, ast_data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if this strategy can process the given AST.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            True if this strategy can process the AST, False otherwise
        """
        return True


class CompositePatternStrategy(ASTProcessingStrategy):
    """
    Processing strategy using the Composite Pattern.
    
    Best for medium-sized ASTs that benefit from the Composite Pattern's
    unified interface for traversing composite and leaf nodes.
    """
    
    def process_ast(self, ast_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AST using the Composite Pattern.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            Dictionary with processing results
        """
        # Extract context information
        file_path = ast_data.get("file_path", "")
        language = ast_data.get("language", "unknown")
        repository = context.get("repository", "")
        file_id = context.get("file_id", "")
        
        try:
            # Create AST composite structure
            ast_root = ASTComposite.create_from_dict(ast_data)
            
            # Process functions with visitor
            function_visitor = FunctionVisitor()
            ast_root.accept(function_visitor)
            functions = function_visitor.get_result()
            
            # Process calls with visitor if enabled
            call_sites = []
            if context.get("create_placeholders", True):
                call_visitor = CallVisitor()
                ast_root.accept(call_visitor)
                call_sites = call_visitor.get_result()
            
            # Process imports with visitor if enabled
            import_sites = []
            if context.get("create_placeholders", True):
                import_visitor = ImportVisitor()
                ast_root.accept(import_visitor)
                import_sites = import_visitor.get_result()
            
            return {
                "status": "success",
                "file_id": file_id,
                "functions": functions,
                "call_sites": call_sites,
                "import_sites": import_sites,
                "strategy": "composite_pattern"
            }
            
        except Exception as e:
            self.logger.exception(f"Error processing AST with Composite Pattern: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path,
                "strategy": "composite_pattern"
            }
    
    @classmethod
    def can_process(cls, ast_data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if this strategy can process the given AST.
        
        Suitable for medium-sized ASTs (100KB-500KB).
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            True if this strategy can process the AST, False otherwise
        """
        file_size = ast_data.get("file_size", 0)
        return 100000 <= file_size <= 500000


class InMemoryIteratorStrategy(ASTProcessingStrategy):
    """
    Processing strategy using the In-Memory Iterator Pattern.
    
    Best for moderately large ASTs that benefit from incremental traversal
    but still fit in memory.
    """
    
    def process_ast(self, ast_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AST using the In-Memory Iterator Pattern.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            Dictionary with processing results
        """
        # Extract context information
        file_path = ast_data.get("file_path", "")
        language = ast_data.get("language", "unknown")
        repository = context.get("repository", "")
        file_id = context.get("file_id", "")
        
        try:
            # Create AST iterator
            ast_iterator = ASTIteratorFactory.create_iterator(
                ast_data=ast_data,
                iterator_type="dict",
                traverse_mode="depth_first"
            )
            
            # Process functions
            functions = []
            for func_node in get_functions(ast_iterator):
                # Extract function info
                function_info = self._extract_function_info(func_node, repository, file_id)
                if function_info:
                    functions.append(function_info)
            
            # Process call sites if enabled
            call_sites = []
            if context.get("create_placeholders", True):
                # Reset iterator for call site processing
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_data,
                    iterator_type="dict",
                    traverse_mode="depth_first"
                )
                
                # Find all call nodes
                for call_node in get_calls(ast_iterator):
                    # Extract call info
                    call_info = self._extract_call_info(call_node, repository)
                    if call_info:
                        call_sites.append(call_info)
            
            # Process import sites if enabled
            import_sites = []
            if context.get("create_placeholders", True):
                # Reset iterator for import processing
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_data,
                    iterator_type="dict",
                    traverse_mode="depth_first"
                )
                
                # Find all import nodes
                for import_node in get_imports(ast_iterator):
                    # Extract import info
                    import_info = self._extract_import_info(import_node, repository)
                    if import_info:
                        import_sites.append(import_info)
            
            return {
                "status": "success",
                "file_id": file_id,
                "functions": functions,
                "call_sites": call_sites,
                "import_sites": import_sites,
                "strategy": "in_memory_iterator"
            }
            
        except Exception as e:
            self.logger.exception(f"Error processing AST with In-Memory Iterator: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path,
                "strategy": "in_memory_iterator"
            }
    
    def _extract_function_info(self, func_node: Dict[str, Any], repository: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract function information from a node.
        """
        # Implementation details omitted for brevity
        # This would be similar to the one in enhanced_graph_builder.py
        return None
    
    def _extract_call_info(self, call_node: Dict[str, Any], repository: str) -> Optional[Dict[str, Any]]:
        """
        Extract call information from a node.
        """
        # Implementation details omitted for brevity
        return None
    
    def _extract_import_info(self, import_node: Dict[str, Any], repository: str) -> Optional[Dict[str, Any]]:
        """
        Extract import information from a node.
        """
        # Implementation details omitted for brevity
        return None
    
    @classmethod
    def can_process(cls, ast_data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if this strategy can process the given AST.
        
        Suitable for moderately large ASTs (500KB-5MB).
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            True if this strategy can process the AST, False otherwise
        """
        file_size = ast_data.get("file_size", 0)
        return 500000 <= file_size <= 5000000


class StreamingIteratorStrategy(ASTProcessingStrategy):
    """
    Processing strategy using the Streaming Iterator Pattern.
    
    Best for very large ASTs that don't fit in memory and need to be
    processed incrementally from a file.
    """
    
    def process_ast(self, ast_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AST using the Streaming Iterator Pattern.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            Dictionary with processing results
        """
        # Extract context information
        file_path = ast_data.get("file_path", "")
        language = ast_data.get("language", "unknown")
        repository = context.get("repository", "")
        file_id = context.get("file_id", "")
        
        try:
            # Get AST file path
            ast_file_path = ast_data.get("file_path_ast")
            if not ast_file_path or not os.path.exists(ast_file_path):
                return {
                    "status": "error",
                    "error": "AST file path not provided or file does not exist",
                    "file_path": file_path,
                    "strategy": "streaming_iterator"
                }
            
            # Create streaming AST iterator
            ast_iterator = ASTIteratorFactory.create_iterator(
                ast_data=ast_file_path,
                iterator_type="streaming",
                chunk_size=1000  # Process 1000 lines at a time
            )
            
            # Process functions
            functions = []
            for func_node in get_functions(ast_iterator):
                # Extract function info
                function_info = self._extract_function_info(func_node, repository, file_id)
                if function_info:
                    functions.append(function_info)
                    
                    # Batch process periodically for better performance
                    if len(functions) >= 100:
                        # In a real implementation, we would batch create nodes here
                        pass
            
            # Process call sites if enabled
            call_sites = []
            if context.get("create_placeholders", True):
                # Reset iterator for call site processing
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_file_path,
                    iterator_type="streaming",
                    chunk_size=1000
                )
                
                # Find all call nodes
                for call_node in get_calls(ast_iterator):
                    # Extract call info
                    call_info = self._extract_call_info(call_node, repository)
                    if call_info:
                        call_sites.append(call_info)
                        
                        # Batch process periodically
                        if len(call_sites) >= 100:
                            # In a real implementation, we would batch create nodes here
                            pass
            
            # Process import sites if enabled
            import_sites = []
            if context.get("create_placeholders", True):
                # Reset iterator for import processing
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_file_path,
                    iterator_type="streaming",
                    chunk_size=1000
                )
                
                # Find all import nodes
                for import_node in get_imports(ast_iterator):
                    # Extract import info
                    import_info = self._extract_import_info(import_node, repository)
                    if import_info:
                        import_sites.append(import_info)
                        
                        # Batch process periodically
                        if len(import_sites) >= 100:
                            # In a real implementation, we would batch create nodes here
                            pass
            
            return {
                "status": "success",
                "file_id": file_id,
                "functions": functions,
                "call_sites": call_sites,
                "import_sites": import_sites,
                "strategy": "streaming_iterator"
            }
            
        except Exception as e:
            self.logger.exception(f"Error processing AST with Streaming Iterator: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path,
                "strategy": "streaming_iterator"
            }
    
    def _extract_function_info(self, func_node: Dict[str, Any], repository: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract function information from a node.
        """
        # Implementation details omitted for brevity
        return None
    
    def _extract_call_info(self, call_node: Dict[str, Any], repository: str) -> Optional[Dict[str, Any]]:
        """
        Extract call information from a node.
        """
        # Implementation details omitted for brevity
        return None
    
    def _extract_import_info(self, import_node: Dict[str, Any], repository: str) -> Optional[Dict[str, Any]]:
        """
        Extract import information from a node.
        """
        # Implementation details omitted for brevity
        return None
    
    @classmethod
    def can_process(cls, ast_data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if this strategy can process the given AST.
        
        Suitable for very large ASTs (>5MB) that have a file representation.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            True if this strategy can process the AST, False otherwise
        """
        file_size = ast_data.get("file_size", 0)
        ast_file_path = ast_data.get("file_path_ast")
        return file_size > 5000000 and ast_file_path and os.path.exists(ast_file_path)


class StandardProcessingStrategy(ASTProcessingStrategy):
    """
    Standard processing strategy using direct traversal.
    
    Best for small ASTs that don't need specialized handling.
    """
    
    def process_ast(self, ast_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AST using standard direct traversal.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            Dictionary with processing results
        """
        # Extract context information
        file_path = ast_data.get("file_path", "")
        language = ast_data.get("language", "unknown")
        repository = context.get("repository", "")
        file_id = context.get("file_id", "")
        
        try:
            # Handle different AST formats (tree-sitter vs native)
            if "root" in ast_data:
                ast_root = ast_data.get("root", {})
                ast_format = "native"
            else:
                # For tree-sitter ASTs, check if it has the expected structure
                if "type" in ast_data and "children" in ast_data:
                    ast_root = ast_data  # The AST itself is the root
                    ast_format = "tree-sitter"
                else:
                    ast_root = {}
                    ast_format = "unknown"
            
            # Add AST format information for downstream processing
            ast_data["_ast_format"] = ast_format
            ast_root["_ast_format"] = ast_format
            
            # Extract functions and classes from the AST
            functions = self._extract_functions(ast_root, file_id, file_path, language, repository)
            classes = self._extract_classes(ast_root, file_id, file_path, language, repository)
            
            # Extract call sites and import sites if placeholders are enabled
            call_sites = []
            import_sites = []
            if context.get("create_placeholders", True):
                call_sites = self._extract_call_sites(ast_root, file_id, repository)
                import_sites = self._extract_import_sites(ast_root, file_id, repository)
            
            return {
                "status": "success",
                "file_id": file_id,
                "functions": functions,
                "classes": classes,
                "call_sites": call_sites,
                "import_sites": import_sites,
                "strategy": "standard"
            }
            
        except Exception as e:
            self.logger.exception(f"Error processing AST with Standard Processing: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path,
                "strategy": "standard"
            }
    
    def _extract_functions(self, ast_root: Dict[str, Any], file_id: str, 
                          file_path: str, language: str, repository: str) -> List[Dict[str, Any]]:
        """
        Extract functions from the AST.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            file_path: Path to the file
            language: Programming language
            repository: Repository name
            
        Returns:
            List of function data dictionaries
        """
        import hashlib
        from code_indexer.utils.ast_utils import get_function_info
        from code_indexer.ingestion.direct.enhanced_graph_builder import find_entity_in_ast
        
        functions = []
        
        # Find function nodes in the AST (use tree-sitter format for now)
        function_nodes = find_entity_in_ast(ast_root, "function_definition")
        
        for function_node in function_nodes:
            # Extract function information
            function_info = get_function_info(function_node)
            
            if not function_info.get("name"):
                continue
                
            # Determine if this is a method (within a class)
            is_method = function_info.get("is_method", False)
            class_id = ""
            class_name = ""
            
            if is_method:
                class_name = function_info.get("class_name", "")
                if class_name:
                    class_id = hashlib.md5(f"{file_id}:{class_name}".encode()).hexdigest()
            
            # Generate a unique ID for the function
            function_id = hashlib.md5(
                f"{file_id}:{function_info['name']}:{class_id}".encode()
            ).hexdigest()
            
            # Create function data dict
            function_data = {
                "id": function_id,
                "name": function_info.get("name", ""),
                "docstring": function_info.get("docstring", ""),
                "start_line": function_info.get("start_line", 0),
                "end_line": function_info.get("end_line", 0),
                "params": function_info.get("params", []),
                "return_type": function_info.get("return_type", ""),
                "file_id": file_id,
                "repository": repository,
                "class_id": class_id,
                "class_name": class_name,
                "is_method": is_method
            }
            
            functions.append(function_data)
        
        return functions
    
    def _extract_classes(self, ast_root: Dict[str, Any], file_id: str,
                        file_path: str, language: str, repository: str) -> List[Dict[str, Any]]:
        """
        Extract classes from the AST.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            file_path: Path to the file
            language: Programming language
            repository: Repository name
            
        Returns:
            List of class data dictionaries
        """
        import hashlib
        from code_indexer.utils.ast_utils import get_class_info
        from code_indexer.ingestion.direct.enhanced_graph_builder import find_entity_in_ast
        
        classes = []
        
        # Find class nodes in the AST (use tree-sitter format for now)
        class_nodes = find_entity_in_ast(ast_root, "class_definition")
        
        for class_node in class_nodes:
            # Extract class information
            class_info = get_class_info(class_node)
            
            if not class_info.get("name"):
                continue
                
            # Generate a unique ID for the class
            class_id = hashlib.md5(f"{file_id}:{class_info['name']}".encode()).hexdigest()
            
            # Create class data dict
            class_data = {
                "id": class_id,
                "name": class_info.get("name", ""),
                "docstring": class_info.get("docstring", ""),
                "start_line": class_info.get("start_line", 0),
                "end_line": class_info.get("end_line", 0),
                "file_id": file_id,
                "repository": repository,
                "parents": class_info.get("parents", [])
            }
            
            classes.append(class_data)
        
        return classes
    
    def _extract_call_sites(self, ast_root: Dict[str, Any], file_id: str, repository: str) -> List[Dict[str, Any]]:
        """
        Extract call sites from the AST.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            repository: Repository name
            
        Returns:
            List of call site data dictionaries
        """
        # Placeholder implementation - would extract calls in real system
        return []
    
    def _extract_import_sites(self, ast_root: Dict[str, Any], file_id: str, repository: str) -> List[Dict[str, Any]]:
        """
        Extract import sites from the AST.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file node
            repository: Repository name
            
        Returns:
            List of import site data dictionaries
        """
        # Placeholder implementation - would extract imports in real system
        return []
    
    @classmethod
    def can_process(cls, ast_data: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if this strategy can process the given AST.
        
        This is the default strategy for small ASTs (<100KB).
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            True if this strategy can process the AST, False otherwise
        """
        file_size = ast_data.get("file_size", 0)
        return file_size < 100000


class ASTProcessingStrategyFactory:
    """
    Factory for creating AST processing strategies.
    
    Implements the Factory Pattern to create the most appropriate
    processing strategy based on AST characteristics.
    """
    
    # Register all available strategies
    _strategies = [
        StreamingIteratorStrategy,
        InMemoryIteratorStrategy,
        CompositePatternStrategy,
        StandardProcessingStrategy  # Default strategy as fallback
    ]
    
    @classmethod
    def create_strategy(cls, ast_data: Dict[str, Any], context: Dict[str, Any]) -> ASTProcessingStrategy:
        """
        Create the most appropriate processing strategy.
        
        Args:
            ast_data: AST data dictionary
            context: Processing context information
            
        Returns:
            The most appropriate ASTProcessingStrategy
        """
        # Override with explicit strategy if specified
        explicit_strategy = context.get("processing_strategy")
        if explicit_strategy:
            for strategy_cls in cls._strategies:
                if strategy_cls.__name__.lower() == explicit_strategy.lower():
                    return strategy_cls(context.get("config", {}))
        
        # TEMPORARY FIX: Always use StandardProcessingStrategy to bypass visitor issues
        return StandardProcessingStrategy(context.get("config", {}))
        
        # Try all strategies in order of registration
        for strategy_cls in cls._strategies:
            if strategy_cls.can_process(ast_data, context):
                return strategy_cls(context.get("config", {}))
        
        # Fallback to standard processing if no strategy can process
        return StandardProcessingStrategy(context.get("config", {}))