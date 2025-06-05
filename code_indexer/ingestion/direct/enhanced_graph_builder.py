"""
Enhanced Graph Builder with Call and Import Sites

An enhanced implementation of the graph builder that includes support for
placeholders for call sites and import sites, enabling accurate cross-file
relationship resolution.
"""

import os
import sys
import logging
import time
import hashlib
import multiprocessing
from typing import Dict, List, Any, Optional, Tuple, Union

# Import direct implementation modules
from code_indexer.ingestion.direct.graph_builder import DirectGraphBuilderRunner, Neo4jToolWrapper
from code_indexer.ingestion.direct.neo4j_tool import DirectNeo4jTool
from code_indexer.utils.ast_utils import get_function_info, get_class_info
from code_indexer.utils.batch_processor import BatchProcessor, BatchProcessorFactory
from code_indexer.utils.neo4j_batch import Neo4jBatchProcessor, batch_create_nodes, batch_create_relationships
from code_indexer.utils.graph_commands import (
    GraphCommand, CreateNodesCommand, CreateRelationshipsCommand, 
    DeleteNodesCommand, GraphCommandInvoker
)
from code_indexer.utils.ast_composite import ASTComposite, ASTNode, CompositeNode, LeafNode
from code_indexer.utils.ast_visitor import ASTVisitor, CallVisitor, FunctionVisitor, ImportVisitor
from code_indexer.utils.ast_iterator import (
    ASTIterator, DictASTIterator, StreamingASTIterator, ASTIteratorFactory,
    find_nodes_by_type, get_functions, get_calls, get_imports
)
from code_indexer.utils.ast_strategy import (
    ASTProcessingStrategy, ASTProcessingStrategyFactory,
    StandardProcessingStrategy, CompositePatternStrategy, 
    InMemoryIteratorStrategy, StreamingIteratorStrategy
)
from code_indexer.utils.indexing_observer import (
    IndexingEvent, IndexingEventType, IndexingObserver,
    ConsoleIndexingObserver, FileIndexingObserver, StatisticsIndexingObserver,
    ProgressBarIndexingObserver, IndexingObserverManager
)

# Import original find_entity_in_ast but we'll define an enhanced version
from code_indexer.utils.ast_utils import find_entity_in_ast as original_find_entity_in_ast

def find_entity_in_ast(ast_dict: Dict[str, Any], entity_type: str) -> List[Dict[str, Any]]:
    """
    Enhanced version of find_entity_in_ast that handles both native and tree-sitter AST formats.
    
    Args:
        ast_dict: Dictionary representation of an AST
        entity_type: Type of entity to find (e.g., "FunctionDef", "ClassDef", "Call")
        
    Returns:
        List of matching entities
    """
    results = []
    
    if not ast_dict or not isinstance(ast_dict, dict):
        return results
    
    # Determine the AST format - check for tree-sitter indicators
    ast_format = ast_dict.get("_ast_format")
    if not ast_format:
        # Auto-detect based on parser info or AST structure
        if ast_dict.get("parser") == "tree-sitter":
            ast_format = "tree-sitter"
        elif "start_byte" in ast_dict and "end_byte" in ast_dict:
            ast_format = "tree-sitter"
        else:
            ast_format = "native"
    
    # Handle tree-sitter AST format with special mappings
    if ast_format == "tree-sitter":
        # Type mappings for tree-sitter to native AST types
        type_mappings = {
            "Function": "function_definition",
            "FunctionDef": "function_definition",
            "Class": "class_definition",
            "ClassDef": "class_definition",
            "Call": "call",
            "Import": "import_statement",
            "ImportFrom": "import_from_statement"
        }
        
        # Get the tree-sitter equivalent type
        ts_entity_type = type_mappings.get(entity_type, entity_type.lower())
        
        # Check if this node matches
        if ast_dict.get("type") == ts_entity_type:
            results.append(ast_dict)
        
        # Check children (if available)
        for child in ast_dict.get("children", []):
            if isinstance(child, dict):
                # Pass along the AST format information
                if "_ast_format" not in child:
                    child["_ast_format"] = ast_format
                results.extend(find_entity_in_ast(child, entity_type))
                
    else:
        # Use the original implementation for native AST format
        results = original_find_entity_in_ast(ast_dict, entity_type)
    
    return results


class EnhancedNeo4jTool(Neo4jToolWrapper):
    """
    Enhanced Neo4j Tool with support for call sites and cross-file relationship resolution.
    """
    
    def clear_repository_data(self, repository: str) -> bool:
        """
        Clear all data for a specific repository.
        
        Args:
            repository: Repository name/identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            self.connect()
            
        if not self.driver:
            self.logger.error("Cannot clear repository data: Neo4j connection not available")
            return False
            
        # Delete all nodes and relationships for this repository
        query = """
        MATCH (n)
        WHERE n.repository = $repository OR n.repository_name = $repository
        DETACH DELETE n
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, repository=repository)
                summary = result.consume()
                self.logger.info(f"Cleared repository data for {repository}: {summary.counters}")
                return True
        except Exception as e:
            self.logger.error(f"Error clearing repository data: {e}")
            return False
    
    def create_call_site_node(self, call_id: str, caller_file_id: str, caller_function_id: Optional[str],
                             caller_class_id: Optional[str], call_name: str, call_module: Optional[str],
                             start_line: int, start_col: int, end_line: int, end_col: int,
                             is_attribute_call: bool = False) -> str:
        """
        Create a CallSite node in the graph.
        
        Args:
            call_id: Unique identifier for the call site
            caller_file_id: ID of the file containing the call site
            caller_function_id: ID of the function containing the call site (optional)
            caller_class_id: ID of the class containing the call site (optional)
            call_name: Name of the function/method being called
            call_module: Module qualifier for the call (optional)
            start_line: Starting line number
            start_col: Starting column number
            end_line: Ending line number
            end_col: Ending column number
            is_attribute_call: Whether this is an attribute call (obj.method())
            
        Returns:
            ID of the created CallSite node
        """
        if not self.driver:
            self.connect()
        
        query = """
        MERGE (cs:CallSite {id: $call_id})
        SET cs.caller_file_id = $caller_file_id,
            cs.caller_function_id = $caller_function_id,
            cs.caller_class_id = $caller_class_id,
            cs.call_name = $call_name,
            cs.call_module = $call_module,
            cs.start_line = $start_line,
            cs.start_col = $start_col,
            cs.end_line = $end_line,
            cs.end_col = $end_col,
            cs.is_attribute_call = $is_attribute_call,
            cs.last_updated = timestamp()
        WITH cs
        MATCH (f:File {id: $caller_file_id})
        MERGE (f)-[:CONTAINS]->(cs)
        """
        
        # Add relationship to containing function if provided
        if caller_function_id:
            query += """
            WITH cs
            MATCH (func:Function {id: $caller_function_id})
            MERGE (func)-[:CONTAINS]->(cs)
            """
        
        # Add relationship to containing class if provided
        if caller_class_id:
            query += """
            WITH cs
            MATCH (cls:Class {id: $caller_class_id})
            MERGE (cls)-[:CONTAINS]->(cs)
            """
        
        query += "RETURN cs.id"
        
        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                call_id=call_id,
                caller_file_id=caller_file_id,
                caller_function_id=caller_function_id,
                caller_class_id=caller_class_id,
                call_name=call_name,
                call_module=call_module,
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
                is_attribute_call=is_attribute_call
            )
            return result.single()[0]
    
    def create_import_site_node(self, import_id: str, file_id: str, import_name: str,
                              module_name: Optional[str], alias: Optional[str],
                              is_from_import: bool, start_line: int, end_line: int) -> str:
        """
        Create an ImportSite node in the graph.
        
        Args:
            import_id: Unique identifier for the import site
            file_id: ID of the file containing the import site
            import_name: Name of the imported entity
            module_name: Name of the module being imported from (optional)
            alias: Alias used for the import (optional)
            is_from_import: Whether this is a from-import statement
            start_line: Starting line number
            end_line: Ending line number
            
        Returns:
            ID of the created ImportSite node
        """
        if not self.driver:
            self.connect()
        
        query = """
        MERGE (i:ImportSite {id: $import_id})
        SET i.file_id = $file_id,
            i.import_name = $import_name,
            i.module_name = $module_name,
            i.alias = $alias,
            i.is_from_import = $is_from_import,
            i.start_line = $start_line,
            i.end_line = $end_line,
            i.last_updated = timestamp()
        WITH i
        MATCH (f:File {id: $file_id})
        MERGE (f)-[:CONTAINS]->(i)
        RETURN i.id
        """
        
        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                import_id=import_id,
                file_id=file_id,
                import_name=import_name,
                module_name=module_name,
                alias=alias,
                is_from_import=is_from_import,
                start_line=start_line,
                end_line=end_line
            )
            return result.single()[0]
    
    def create_resolves_to_relationship(self, source_id: str, target_id: str,
                                       score: float = 1.0) -> bool:
        """
        Create a RESOLVES_TO relationship between a placeholder and its target.
        
        Args:
            source_id: ID of the source node (CallSite or ImportSite)
            target_id: ID of the target node (Function, Class, etc.)
            score: Confidence score for the resolution (0.0-1.0)
            
        Returns:
            True if relationship was created, False otherwise
        """
        query = """
        MATCH (source) WHERE source.id = $source_id
        MATCH (target) WHERE target.id = $target_id
        MERGE (source)-[r:RESOLVES_TO]->(target)
        SET r.score = $score,
            r.timestamp = timestamp()
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                session.run(
                    query,
                    source_id=source_id,
                    target_id=target_id,
                    score=score
                )
            return True
        except Exception as e:
            self.logger.error(f"Error creating RESOLVES_TO relationship: {e}")
            return False
    
    def setup_optimized_schema(self) -> None:
        """Setup Neo4j schema with composite indices for optimized resolution."""
        # Create constraints and composite indices
        schema_commands = [
            # Ensure unique IDs for all nodes
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:CallSite) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ImportSite) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SymIndex) REQUIRE n.id IS UNIQUE",
            
            # Composite indices for efficient resolution
            "CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.file_id)",
            "CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.class_id)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name, c.file_id)",
            
            # Indices for call site and import site nodes
            "CREATE INDEX IF NOT EXISTS FOR (c:CallSite) ON (c.call_name, c.call_module)",
            "CREATE INDEX IF NOT EXISTS FOR (i:ImportSite) ON (i.import_name, i.module_name)",
            
            # Index for SymIndex nodes (for the sharded strategy)
            "CREATE INDEX IF NOT EXISTS FOR (s:SymIndex) ON (s.repo, s.name)"
        ]
        
        for command in schema_commands:
            try:
                self.execute_cypher(command)
            except Exception as e:
                self.logger.error(f"Error creating schema: {e}")


class EnhancedGraphBuilderRunner(DirectGraphBuilderRunner):
    """
    Enhanced Graph Builder with support for call sites and cross-file resolution.
    
    This extends the DirectGraphBuilder to implement the placeholder pattern
    for CallSites and ImportSites, allowing accurate cross-file relationship
    resolution without external caching services.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the enhanced graph builder.
        
        Args:
            config: Configuration dictionary
        """
        # Initialize base class
        super().__init__(config)
        
        # Override Neo4j tool with enhanced version
        self.neo4j_tool = EnhancedNeo4jTool(self.config.get("neo4j_config", {}))
        
        # Create command invoker for transaction management
        self.command_invoker = GraphCommandInvoker()
        
        # Additional configuration
        self.create_placeholders = self.config.get("create_placeholders", True)
        self.resolution_strategy = self.config.get("resolution_strategy", "join")
        self.immediate_resolution = self.config.get("immediate_resolution", True)
        self.use_command_pattern = self.config.get("use_command_pattern", True)
        self.use_composite_pattern = self.config.get("use_composite_pattern", True)
        self.use_iterator_pattern = self.config.get("use_iterator_pattern", True)
        self.use_strategy_pattern = self.config.get("use_strategy_pattern", True)
        self.use_observer_pattern = self.config.get("use_observer_pattern", True)
        
        # Strategy pattern configuration
        self.default_processing_strategy = self.config.get("default_processing_strategy", None)
        self.strategy_config = self.config.get("strategy_config", {})
        
        # Set up optimized schema
        if self.neo4j_tool.connect():
            self.neo4j_tool.setup_optimized_schema()
            self.logger.info("Enhanced Neo4j schema setup complete")
        
        # Additional graph statistics
        self.graph_stats.update({
            "call_sites": 0,
            "import_sites": 0,
            "resolved_calls": 0,
            "resolved_imports": 0,
            "commands_executed": 0,
            "visitor_calls": 0,
            "iterator_calls": 0,
            "strategy_calls": 0
        })
        
        # Set up observer pattern
        self.observer_manager = IndexingObserverManager()
        self._setup_observers()
    
    def _extract_call_sites(self, ast_root: Dict[str, Any], file_id: str, 
                          repository: str = "",
                          current_function: Optional[Dict[str, Any]] = None, 
                          current_class: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract call sites from the AST and create placeholder nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file
            repository: Repository name
            current_function: Current function context if inside a function
            current_class: Current class context if inside a class
            
        Returns:
            List of created call site nodes
        """
        call_sites = []
        
        # Find Call nodes in the AST
        call_nodes = find_entity_in_ast(ast_root, "Call")
        
        # Detect AST format
        ast_format = ast_root.get("_ast_format", "native")
        repository = ""  # This will be filled in later
        
        for call_node in call_nodes:
            # Extract function info based on AST format
            if ast_format == "native":
                # Native AST format
                if "func" not in call_node.get("attributes", {}):
                    continue
                
                func = call_node["attributes"]["func"]
                
                # Get position info
                start_pos = call_node.get("start_position", {})
                end_pos = call_node.get("end_position", {})
                
                start_line = start_pos.get("row", 0)
                start_col = start_pos.get("column", 0)
                end_line = end_pos.get("row", 0)
                end_col = end_pos.get("column", 0)
                
            elif ast_format == "tree-sitter":
                # Tree-sitter AST format
                # In tree-sitter format, the function reference is usually the first child
                if not call_node.get("children") or len(call_node["children"]) < 1:
                    continue
                
                # The first child should be the function reference (identifier or attribute)
                func = call_node["children"][0]
                
                # Get position info from tree-sitter format
                start_point = call_node.get("start_point", {})
                end_point = call_node.get("end_point", {})
                
                if isinstance(start_point, dict):
                    start_line = start_point.get("row", 0)
                    start_col = start_point.get("column", 0)
                else:
                    # Handle case where it might be a tuple instead of dict
                    start_line = start_point[0] if isinstance(start_point, (list, tuple)) and len(start_point) > 0 else 0
                    start_col = start_point[1] if isinstance(start_point, (list, tuple)) and len(start_point) > 1 else 0
                
                if isinstance(end_point, dict):
                    end_line = end_point.get("row", 0)
                    end_col = end_point.get("column", 0)
                else:
                    # Handle case where it might be a tuple instead of dict
                    end_line = end_point[0] if isinstance(end_point, (list, tuple)) and len(end_point) > 0 else 0
                    end_col = end_point[1] if isinstance(end_point, (list, tuple)) and len(end_point) > 1 else 0
            else:
                # Unknown format, skip this call node
                self.logger.warning(f"Unknown AST format: {ast_format}, skipping call node")
                continue
            
            # Get current context
            caller_function_id = current_function.get("id") if current_function else None
            caller_class_id = current_class.get("id") if current_class else None
            
            # Extract call details
            call_info = self._extract_call_info(func, ast_format=ast_format)
            
            if call_info:
                # Generate a unique ID for the call site that includes repository information
                # This ensures uniqueness across repositories even if file paths are similar
                # Use repository parameter which is passed in from _process_ast method
                # Also check if repository info is in ast_root as a fallback
                if not repository:
                    repository = ast_root.get("repository", "")
                call_id = hashlib.md5(
                    f"{repository}:{file_id}:{start_line}:{start_col}:{call_info['name']}".encode()
                ).hexdigest()
                
                # Create call site node
                self.neo4j_tool.create_call_site_node(
                    call_id=call_id,
                    caller_file_id=file_id,
                    caller_function_id=caller_function_id,
                    caller_class_id=caller_class_id,
                    call_name=call_info["name"],
                    call_module=call_info.get("module"),
                    start_line=start_line,
                    start_col=start_col,
                    end_line=end_line,
                    end_col=end_col,
                    is_attribute_call=call_info.get("is_attribute", False)
                )
                
                # Add call site to result list
                call_sites.append({
                    "id": call_id,
                    "name": call_info["name"],
                    "module": call_info.get("module"),
                    "start_line": start_line,
                    "end_line": end_line,
                    "is_attribute": call_info.get("is_attribute", False)
                })
                
                self.graph_stats["call_sites"] += 1
                
                # Attempt immediate resolution if configured
                if self.immediate_resolution:
                    self._resolve_call_site(call_id, call_info, file_id)
        
        return call_sites
    
    def _extract_call_info(self, func_node: Dict[str, Any], ast_format: str = "native") -> Optional[Dict[str, Any]]:
        """
        Extract call information from a function node.
        
        Args:
            func_node: The function node from a Call AST
            ast_format: Format of the AST ("native" or "tree-sitter")
            
        Returns:
            Dictionary with call information or None
        """
        if not func_node:
            return None
        
        node_type = func_node.get("type")
        
        if ast_format == "native":
            # Native AST format
            if node_type == "Name":
                # Simple function call: function_name()
                return {
                    "name": func_node.get("attributes", {}).get("id", ""),
                    "is_attribute": False
                }
                
            elif node_type == "Attribute":
                # Method call: object.method()
                attrs = func_node.get("attributes", {})
                method_name = attrs.get("attr", "")
                value = attrs.get("value", {})
                
                if value.get("type") == "Name":
                    # Simple attribute: object.method()
                    return {
                        "name": method_name,
                        "module": value.get("attributes", {}).get("id", ""),
                        "is_attribute": True
                    }
                elif value.get("type") == "Attribute":
                    # Nested attribute: module.class.method()
                    nested_value = value.get("attributes", {})
                    obj_name = nested_value.get("attr", "")
                    return {
                        "name": method_name,
                        "module": obj_name,
                        "is_attribute": True
                    }
        
        elif ast_format == "tree-sitter":
            # Tree-sitter AST format
            if node_type == "identifier":
                # Simple function call: function_name()
                # In tree-sitter, the name is usually in the "text" field
                return {
                    "name": func_node.get("text", ""),
                    "is_attribute": False
                }
                
            elif node_type == "attribute":
                # Method call: object.method()
                # With tree-sitter, attribute nodes have children
                if not func_node.get("children") or len(func_node["children"]) < 3:
                    return None
                
                # The children structure is usually: [object, ".", method]
                obj_node = func_node["children"][0]
                method_node = func_node["children"][2]
                
                if method_node.get("type") == "identifier":
                    method_name = method_node.get("text", "")
                    
                    if obj_node.get("type") == "identifier":
                        # Simple attribute: object.method()
                        obj_name = obj_node.get("text", "")
                        return {
                            "name": method_name,
                            "module": obj_name,
                            "is_attribute": True
                        }
                    elif obj_node.get("type") == "attribute":
                        # Nested attribute: module.class.method()
                        if obj_node.get("children") and len(obj_node["children"]) >= 3:
                            class_node = obj_node["children"][2]
                            class_name = class_node.get("text", "")
                            return {
                                "name": method_name,
                                "module": class_name,
                                "is_attribute": True
                            }
        
        return None
    
    def _extract_import_sites(self, ast_root: Dict[str, Any], file_id: str, repository: str = "") -> List[Dict[str, Any]]:
        """
        Extract import sites from the AST and create placeholder nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file
            repository: Repository name
            
        Returns:
            List of created import site nodes
        """
        import_sites = []
        repository = ""  # This will be filled in later
        
        # Detect AST format
        ast_format = ast_root.get("_ast_format", "native")
        
        # Find Import and ImportFrom nodes
        import_nodes = find_entity_in_ast(ast_root, "Import")
        import_from_nodes = find_entity_in_ast(ast_root, "ImportFrom")
        
        # Process Import statements
        for import_node in import_nodes:
            # Extract import information based on AST format
            if ast_format == "native":
                # Native AST format
                if "names" not in import_node.get("attributes", {}):
                    continue
                    
                start_pos = import_node.get("start_position", {})
                end_pos = import_node.get("end_position", {})
                
                start_line = start_pos.get("row", 0)
                end_line = end_pos.get("row", 0)
                
                import_aliases = import_node["attributes"]["names"]
                
            elif ast_format == "tree-sitter":
                # Tree-sitter AST format
                start_point = import_node.get("start_point", {})
                end_point = import_node.get("end_point", {})
                
                if isinstance(start_point, dict):
                    start_line = start_point.get("row", 0)
                else:
                    start_line = start_point[0] if isinstance(start_point, (list, tuple)) and len(start_point) > 0 else 0
                
                if isinstance(end_point, dict):
                    end_line = end_point.get("row", 0)
                else:
                    end_line = end_point[0] if isinstance(end_point, (list, tuple)) and len(end_point) > 0 else 0
                
                # Extract import names from tree-sitter AST
                # In tree-sitter format, imports are structured differently
                # We need to find dotted_name nodes within the import statement
                import_aliases = []
                for child in import_node.get("children", []):
                    if child.get("type") == "dotted_name":
                        # This is the module being imported
                        name = ""
                        # Collect all identifier texts in the dotted name
                        for part in child.get("children", []):
                            if part.get("type") == "identifier":
                                name = part.get("text", "")
                                import_aliases.append({"name": name, "asname": ""})
                                break
            else:
                # Unknown format, skip this node
                self.logger.warning(f"Unknown AST format: {ast_format}, skipping import node")
                continue
            
            # Process each import name/alias
            for alias in import_aliases:
                name = alias.get("name", "")
                asname = alias.get("asname", "")
                
                if name:
                    # Generate a unique ID for the import site that includes repository information
                    # This ensures uniqueness across repositories even if file paths are similar
                    # Use repository parameter which is passed in from _process_ast method
                    # Also check if repository info is in ast_root as a fallback
                    if not repository:
                        repository = ast_root.get("repository", "")
                    import_id = hashlib.md5(
                        f"{repository}:{file_id}:import:{start_line}:{name}".encode()
                    ).hexdigest()
                    
                    # Create import site node
                    self.neo4j_tool.create_import_site_node(
                        import_id=import_id,
                        file_id=file_id,
                        import_name=name,
                        module_name=None,
                        alias=asname,
                        is_from_import=False,
                        start_line=start_line,
                        end_line=end_line
                    )
                    
                    # Add to result list
                    import_sites.append({
                        "id": import_id,
                        "name": name,
                        "alias": asname,
                        "is_from_import": False,
                        "start_line": start_line,
                        "end_line": end_line
                    })
                    
                    self.graph_stats["import_sites"] += 1
        
        # Process ImportFrom statements
        for import_from_node in import_from_nodes:
            # Extract import information based on AST format
            if ast_format == "native":
                # Native AST format
                if "names" not in import_from_node.get("attributes", {}):
                    continue
                    
                module = import_from_node["attributes"].get("module", "")
                start_pos = import_from_node.get("start_position", {})
                end_pos = import_from_node.get("end_position", {})
                
                start_line = start_pos.get("row", 0)
                end_line = end_pos.get("row", 0)
                
                import_aliases = import_from_node["attributes"]["names"]
                
            elif ast_format == "tree-sitter":
                # Tree-sitter AST format
                start_point = import_from_node.get("start_point", {})
                end_point = import_from_node.get("end_point", {})
                
                if isinstance(start_point, dict):
                    start_line = start_point.get("row", 0)
                else:
                    start_line = start_point[0] if isinstance(start_point, (list, tuple)) and len(start_point) > 0 else 0
                
                if isinstance(end_point, dict):
                    end_line = end_point.get("row", 0)
                else:
                    end_line = end_point[0] if isinstance(end_point, (list, tuple)) and len(end_point) > 0 else 0
                
                # Extract module name from tree-sitter AST
                module = ""
                import_aliases = []
                
                # Find module name
                for child in import_from_node.get("children", []):
                    if child.get("type") == "dotted_name" and child.get("children"):
                        # Collect all identifier texts in the dotted name for the module
                        module_parts = []
                        for part in child.get("children", []):
                            if part.get("type") == "identifier":
                                module_parts.append(part.get("text", ""))
                        module = ".".join(module_parts)
                        break
                
                # Find imported names
                for child in import_from_node.get("children", []):
                    if child.get("type") == "import_items" and child.get("children"):
                        for item in child.get("children", []):
                            if item.get("type") == "dotted_name" and item.get("children"):
                                for name_part in item.get("children", []):
                                    if name_part.get("type") == "identifier":
                                        name = name_part.get("text", "")
                                        import_aliases.append({"name": name, "asname": ""})
                                        break
            else:
                # Unknown format, skip this node
                continue
            
            # Process each import name/alias
            for alias in import_aliases:
                name = alias.get("name", "")
                asname = alias.get("asname", "")
                
                if name and module:
                    # Generate a unique ID for the import site that includes repository information
                    # This ensures uniqueness across repositories even if file paths are similar
                    # Use repository parameter which is passed in from _process_ast method
                    # Also check if repository info is in ast_root as a fallback
                    if not repository:
                        repository = ast_root.get("repository", "")
                    import_id = hashlib.md5(
                        f"{repository}:{file_id}:import_from:{start_line}:{module}.{name}".encode()
                    ).hexdigest()
                    
                    # Create import site node
                    self.neo4j_tool.create_import_site_node(
                        import_id=import_id,
                        file_id=file_id,
                        import_name=name,
                        module_name=module,
                        alias=asname,
                        is_from_import=True,
                        start_line=start_line,
                        end_line=end_line
                    )
                    
                    # Add to result list
                    import_sites.append({
                        "id": import_id,
                        "name": name,
                        "module": module,
                        "alias": asname,
                        "is_from_import": True,
                        "start_line": start_line,
                        "end_line": end_line
                    })
                    
                    self.graph_stats["import_sites"] += 1
        
        return import_sites
    
    def _resolve_call_site(self, call_id: str, call_info: Dict[str, Any], file_id: str) -> bool:
        """
        Resolve a call site to its target function.
        
        Args:
            call_id: ID of the call site
            call_info: Information about the call
            file_id: ID of the file containing the call
            
        Returns:
            True if resolved, False otherwise
        """
        # Based on resolution strategy, use the appropriate query
        if self.resolution_strategy == "join":
            # Use pure Cypher join approach
            return self._resolve_call_site_join(call_id, call_info, file_id)
        elif self.resolution_strategy == "hashmap":
            # Use in-process hash map approach
            return self._resolve_call_site_hashmap(call_id, call_info, file_id)
        elif self.resolution_strategy == "sharded":
            # Use label-sharded index approach
            return self._resolve_call_site_sharded(call_id, call_info, file_id)
        
        # Default to join approach
        return self._resolve_call_site_join(call_id, call_info, file_id)
    
    def _resolve_call_site_join(self, call_id: str, call_info: Dict[str, Any], file_id: str) -> bool:
        """
        Resolve a call site using pure Cypher join.
        
        This approach works well for repositories with up to ~2M definitions.
        
        Args:
            call_id: ID of the call site
            call_info: Information about the call
            file_id: ID of the file containing the call
            
        Returns:
            True if resolved, False otherwise
        """
        call_name = call_info["name"]
        is_attribute = call_info.get("is_attribute", False)
        module_name = call_info.get("module")
        
        if is_attribute and module_name:
            # Method call with object/module
            query = """
            MATCH (cs:CallSite {id: $call_id})
            MATCH (f:Function {name: $call_name})
            // Find classes with the object name
            WITH cs, f
            MATCH (c:Class {name: $module_name})-[:CONTAINS]->(f)
            // Create RESOLVES_TO relationship
            MERGE (cs)-[r:RESOLVES_TO]->(f)
            SET r.score = 1.0, r.timestamp = timestamp()
            RETURN count(r) as rel_count
            """
            
            result = self.neo4j_tool.execute_cypher(query, {
                "call_id": call_id,
                "call_name": call_name,
                "module_name": module_name
            })
            
            if result and result[0]["rel_count"] > 0:
                self.graph_stats["resolved_calls"] += 1
                return True
                
            # Try resolving as a module-qualified function
            query = """
            MATCH (cs:CallSite {id: $call_id})
            MATCH (f:Function {name: $call_name})
            MATCH (i:ImportSite {file_id: $file_id, import_name: $module_name})
            // Create RESOLVES_TO relationship
            MERGE (cs)-[r:RESOLVES_TO]->(f)
            SET r.score = 0.8, r.timestamp = timestamp()
            RETURN count(r) as rel_count
            """
            
            result = self.neo4j_tool.execute_cypher(query, {
                "call_id": call_id,
                "call_name": call_name,
                "module_name": module_name,
                "file_id": file_id
            })
            
            if result and result[0]["rel_count"] > 0:
                self.graph_stats["resolved_calls"] += 1
                return True
        else:
            # Direct function call
            query = """
            MATCH (cs:CallSite {id: $call_id})
            MATCH (f:Function {name: $call_name})
            // Prioritize functions in the same file
            WITH cs, f, 
                 CASE WHEN f.file_id = $file_id THEN 1.0 ELSE 0.7 END as score
            ORDER BY score DESC
            LIMIT 1
            // Create RESOLVES_TO relationship
            MERGE (cs)-[r:RESOLVES_TO]->(f)
            SET r.score = score, r.timestamp = timestamp()
            RETURN count(r) as rel_count
            """
            
            result = self.neo4j_tool.execute_cypher(query, {
                "call_id": call_id,
                "call_name": call_name,
                "file_id": file_id
            })
            
            if result and result[0]["rel_count"] > 0:
                self.graph_stats["resolved_calls"] += 1
                return True
        
        return False
    
    def _resolve_call_site_hashmap(self, call_id: str, call_info: Dict[str, Any], file_id: str) -> bool:
        """
        Resolve a call site using in-process hash map.
        
        This approach is better for repositories with 2-5M definitions.
        First, build an in-memory index of all functions, then use it for resolution.
        
        Args:
            call_id: ID of the call site
            call_info: Information about the call
            file_id: ID of the file containing the call
            
        Returns:
            True if resolved, False otherwise
        """
        # Implementation would fetch all function definitions once
        # and build an in-memory index for faster lookups
        # For now, delegate to the join approach
        return self._resolve_call_site_join(call_id, call_info, file_id)
    
    def _resolve_call_site_sharded(self, call_id: str, call_info: Dict[str, Any], file_id: str) -> bool:
        """
        Resolve a call site using label-sharded indices.
        
        This approach is best for massive repositories with >5M definitions.
        It uses SymIndex nodes with raw node IDs to enable fast lookups
        without loading full Function/Class nodes.
        
        Args:
            call_id: ID of the call site
            call_info: Information about the call
            file_id: ID of the file containing the call
            
        Returns:
            True if resolved, False otherwise
        """
        call_name = call_info["name"]
        is_attribute = call_info.get("is_attribute", False)
        module_name = call_info.get("module")
        
        # First, ensure SymIndex nodes exist for all relevant definitions
        # This is a one-time operation per repository update
        self._ensure_sym_index_nodes()
        
        # Now use the SymIndex nodes for resolution
        if is_attribute and module_name:
            # Method call with object/module
            query = """
            MATCH (cs:CallSite {id: $call_id})
            MATCH (si:SymIndex {name: $call_name})
            WHERE si.class_name = $module_name
            MATCH (f:Function) WHERE id(f) = si.target_id
            // Create RESOLVES_TO relationship
            MERGE (cs)-[r:RESOLVES_TO]->(f)
            SET r.score = 1.0, r.timestamp = timestamp()
            RETURN count(r) as rel_count
            """
            
            result = self.neo4j_tool.execute_cypher(query, {
                "call_id": call_id,
                "call_name": call_name,
                "module_name": module_name
            })
            
            if result and result[0]["rel_count"] > 0:
                self.graph_stats["resolved_calls"] += 1
                return True
                
            # Try resolving as a module-qualified function
            query = """
            MATCH (cs:CallSite {id: $call_id})
            MATCH (si:SymIndex {name: $call_name, module: $module_name})
            MATCH (f:Function) WHERE id(f) = si.target_id
            // Create RESOLVES_TO relationship
            MERGE (cs)-[r:RESOLVES_TO]->(f)
            SET r.score = 0.8, r.timestamp = timestamp()
            RETURN count(r) as rel_count
            """
            
            result = self.neo4j_tool.execute_cypher(query, {
                "call_id": call_id,
                "call_name": call_name,
                "module_name": module_name
            })
            
            if result and result[0]["rel_count"] > 0:
                self.graph_stats["resolved_calls"] += 1
                return True
        else:
            # Direct function call - use SymIndex for lookup
            query = """
            MATCH (cs:CallSite {id: $call_id})
            MATCH (si:SymIndex {name: $call_name})
            WITH cs, si, 
                 CASE WHEN si.file_id = $file_id THEN 1.0 ELSE 0.7 END as score
            ORDER BY score DESC
            LIMIT 1
            MATCH (f:Function) WHERE id(f) = si.target_id
            // Create RESOLVES_TO relationship
            MERGE (cs)-[r:RESOLVES_TO]->(f)
            SET r.score = score, r.timestamp = timestamp()
            RETURN count(r) as rel_count
            """
            
            result = self.neo4j_tool.execute_cypher(query, {
                "call_id": call_id,
                "call_name": call_name,
                "file_id": file_id
            })
            
            if result and result[0]["rel_count"] > 0:
                self.graph_stats["resolved_calls"] += 1
                return True
        
        return False
    
    def _ensure_sym_index_nodes(self) -> None:
        """
        Ensure SymIndex nodes exist for all function and class definitions.
        
        This is typically run once after ingestion but before resolution.
        The SymIndex nodes serve as a lightweight look-up index for fast
        resolution in massive repositories.
        """
        # Skip if index was already created in this session
        if getattr(self, "_sym_index_created", False):
            return
            
        self.logger.info("Creating SymIndex nodes for efficient resolution...")
        
        # Create SymIndex nodes for all functions
        function_index_query = """
        MATCH (f:Function)
        WHERE NOT EXISTS {
            MATCH (si:SymIndex {target_id: id(f)})
        }
        WITH f
        MERGE (si:SymIndex {id: 'sym_' + f.id})
        SET si.name = f.name,
            si.target_id = id(f),
            si.entity_type = 'Function',
            si.file_id = f.file_id,
            si.class_id = f.class_id,
            si.is_method = f.is_method
        WITH count(*) AS indexed
        RETURN indexed
        """
        
        result = self.neo4j_tool.execute_cypher(function_index_query)
        indexed_functions = result[0]["indexed"] if result else 0
        
        # Create SymIndex nodes for all classes
        class_index_query = """
        MATCH (c:Class)
        WHERE NOT EXISTS {
            MATCH (si:SymIndex {target_id: id(c)})
        }
        WITH c
        MERGE (si:SymIndex {id: 'sym_' + c.id})
        SET si.name = c.name,
            si.target_id = id(c),
            si.entity_type = 'Class',
            si.file_id = c.file_id
        WITH count(*) AS indexed
        RETURN indexed
        """
        
        result = self.neo4j_tool.execute_cypher(class_index_query)
        indexed_classes = result[0]["indexed"] if result else 0
        
        # For method calls, we need to associate methods with their classes
        method_class_index_query = """
        MATCH (c:Class)-[:CONTAINS]->(f:Function)
        MATCH (si:SymIndex {target_id: id(f)})
        SET si.class_name = c.name
        WITH count(*) AS indexed
        RETURN indexed
        """
        
        result = self.neo4j_tool.execute_cypher(method_class_index_query)
        indexed_methods = result[0]["indexed"] if result else 0
        
        self.logger.info(f"Created SymIndex for {indexed_functions} functions, {indexed_classes} classes, and updated {indexed_methods} methods")
        
        # Mark as created for this session
        self._sym_index_created = True
    
    def _resolve_all_placeholders(self) -> Dict[str, int]:
        """
        Perform a bulk resolution of all unresolved placeholders.
        
        This method uses the configured resolution strategy to resolve
        all placeholder nodes that have not yet been resolved to their targets.
        
        Returns:
            Dictionary with resolution statistics
        """
        self.logger.info(f"Performing bulk resolution using strategy: {self.resolution_strategy}")
        
        # Choose the appropriate resolution strategy
        if self.resolution_strategy == "hashmap":
            return self._resolve_all_placeholders_hashmap()
        elif self.resolution_strategy == "sharded":
            return self._resolve_all_placeholders_sharded()
        else:
            # Default to pure Cypher join strategy
            return self._resolve_all_placeholders_join()
    
    def _resolve_all_placeholders_join(self) -> Dict[str, int]:
        """
        Perform bulk resolution using pure Cypher join approach.
        
        Suitable for repositories with up to ~2M definitions.
        
        Returns:
            Dictionary with resolution statistics
        """
        # Process in batches to avoid long-running transactions
        batch_size = 5000
        total_resolved_calls = 0
        total_resolved_imports = 0
        
        # Resolve call sites
        while True:
            call_site_query = f"""
            MATCH (cs:CallSite)
            WHERE NOT EXISTS((cs)-[:RESOLVES_TO]->())
            WITH cs LIMIT {batch_size}
            MATCH (f:Function {{name: cs.call_name}})
            WITH cs, f, 
                 CASE WHEN f.file_id = cs.caller_file_id THEN 1.0 ELSE 0.7 END as score
            ORDER BY cs.id, score DESC
            WITH cs, collect({{func: f, score: score}})[0] as best_match
            WITH cs, best_match.func as target_func, best_match.score as match_score
            MERGE (cs)-[r:RESOLVES_TO]->(target_func)
            SET r.score = match_score, r.timestamp = timestamp()
            RETURN count(r) as resolved_calls
            """
            
            call_result = self.neo4j_tool.execute_cypher(call_site_query)
            resolved_calls = call_result[0]["resolved_calls"] if call_result else 0
            total_resolved_calls += resolved_calls
            
            if resolved_calls == 0:
                break
                
            self.logger.info(f"Resolved {resolved_calls} call sites in this batch")
        
        # Resolve import sites
        while True:
            import_site_query = f"""
            MATCH (is:ImportSite)
            WHERE NOT EXISTS((is)-[:RESOLVES_TO]->())
            WITH is LIMIT {batch_size}
            OPTIONAL MATCH (c:Class {{name: is.import_name}})
            WITH is, c
            WHERE c IS NOT NULL
            MERGE (is)-[r:RESOLVES_TO]->(c)
            SET r.score = 1.0, r.timestamp = timestamp()
            RETURN count(r) as resolved_imports
            """
            
            import_result = self.neo4j_tool.execute_cypher(import_site_query)
            resolved_imports = import_result[0]["resolved_imports"] if import_result else 0
            total_resolved_imports += resolved_imports
            
            if resolved_imports == 0:
                break
                
            self.logger.info(f"Resolved {resolved_imports} import sites in this batch")
        
        # Update graph statistics
        self.graph_stats["resolved_calls"] += total_resolved_calls
        self.graph_stats["resolved_imports"] += total_resolved_imports
        
        return {
            "resolved_calls": total_resolved_calls,
            "resolved_imports": total_resolved_imports
        }
    
    def _resolve_all_placeholders_hashmap(self) -> Dict[str, int]:
        """
        Perform bulk resolution using in-process hashmap approach.
        
        Suitable for repositories with 2-5M definitions. Builds an in-memory
        index of all definitions before resolving placeholders.
        
        Returns:
            Dictionary with resolution statistics
        """
        self.logger.info("Building in-memory symbol map for fast resolution...")
        
        # First, build an in-memory map of all definitions
        function_map_query = """
        MATCH (f:Function)
        RETURN f.name as name, 
               f.file_id as file_id, 
               f.class_id as class_id,
               id(f) as node_id
        """
        
        function_map = {}
        function_results = self.neo4j_tool.execute_cypher(function_map_query)
        
        for result in function_results:
            name = result["name"]
            if name not in function_map:
                function_map[name] = []
                
            function_map[name].append({
                "node_id": result["node_id"],
                "file_id": result["file_id"],
                "class_id": result["class_id"]
            })
        
        self.logger.info(f"Built in-memory index with {len(function_map)} function names")
        
        # Process call sites in batches
        batch_size = 5000
        total_resolved_calls = 0
        
        while True:
            # Get a batch of unresolved call sites
            call_sites_query = f"""
            MATCH (cs:CallSite)
            WHERE NOT EXISTS((cs)-[:RESOLVES_TO]->())
            RETURN cs.id as id, 
                   cs.call_name as name,
                   cs.caller_file_id as file_id,
                   cs.call_module as module
            LIMIT {batch_size}
            """
            
            call_sites = self.neo4j_tool.execute_cypher(call_sites_query)
            
            if not call_sites:
                break
                
            # Process this batch
            resolutions = []
            
            for call_site in call_sites:
                call_id = call_site["id"]
                call_name = call_site["name"]
                file_id = call_site["file_id"]
                
                if call_name not in function_map:
                    continue
                    
                # Find best matching function
                candidates = function_map[call_name]
                best_score = 0
                best_node_id = None
                
                for candidate in candidates:
                    # Same file is preferred
                    if candidate["file_id"] == file_id:
                        score = 1.0
                    else:
                        score = 0.7
                        
                    if score > best_score:
                        best_score = score
                        best_node_id = candidate["node_id"]
                
                if best_node_id:
                    resolutions.append({
                        "call_id": call_id,
                        "node_id": best_node_id,
                        "score": best_score
                    })
            
            # Batch create all the RESOLVES_TO relationships
            if resolutions:
                # Create multi-parameter statement with all resolutions
                params = {"resolutions": resolutions}
                
                resolve_query = """
                UNWIND $resolutions AS res
                MATCH (cs:CallSite {id: res.call_id})
                MATCH (f) WHERE id(f) = res.node_id
                MERGE (cs)-[r:RESOLVES_TO]->(f)
                SET r.score = res.score, r.timestamp = timestamp()
                """
                
                self.neo4j_tool.execute_cypher(resolve_query, params)
                total_resolved_calls += len(resolutions)
                
                self.logger.info(f"Resolved {len(resolutions)} call sites in this batch")
                
            if len(call_sites) < batch_size:
                break
        
        # Similarly process import sites (simplified version)
        # Process import sites using similar batch approach
        total_resolved_imports = 0
        
        # Get class map for import resolution
        class_map_query = """
        MATCH (c:Class)
        RETURN c.name as name, id(c) as node_id
        """
        
        class_map = {}
        class_results = self.neo4j_tool.execute_cypher(class_map_query)
        
        for result in class_results:
            class_map[result["name"]] = result["node_id"]
        
        # Process import sites in batches
        while True:
            import_sites_query = f"""
            MATCH (is:ImportSite)
            WHERE NOT EXISTS((is)-[:RESOLVES_TO]->())
            RETURN is.id as id, is.import_name as name
            LIMIT {batch_size}
            """
            
            import_sites = self.neo4j_tool.execute_cypher(import_sites_query)
            
            if not import_sites:
                break
                
            # Process this batch
            resolutions = []
            
            for import_site in import_sites:
                import_id = import_site["id"]
                import_name = import_site["name"]
                
                if import_name in class_map:
                    resolutions.append({
                        "import_id": import_id,
                        "node_id": class_map[import_name],
                        "score": 1.0
                    })
            
            # Batch create all the RESOLVES_TO relationships
            if resolutions:
                # Create multi-parameter statement with all resolutions
                params = {"resolutions": resolutions}
                
                resolve_query = """
                UNWIND $resolutions AS res
                MATCH (is:ImportSite {id: res.import_id})
                MATCH (c) WHERE id(c) = res.node_id
                MERGE (is)-[r:RESOLVES_TO]->(c)
                SET r.score = res.score, r.timestamp = timestamp()
                """
                
                self.neo4j_tool.execute_cypher(resolve_query, params)
                total_resolved_imports += len(resolutions)
                
                self.logger.info(f"Resolved {len(resolutions)} import sites in this batch")
                
            if len(import_sites) < batch_size:
                break
        
        # Update graph statistics
        self.graph_stats["resolved_calls"] += total_resolved_calls
        self.graph_stats["resolved_imports"] += total_resolved_imports
        
        return {
            "resolved_calls": total_resolved_calls,
            "resolved_imports": total_resolved_imports
        }
    
    def _resolve_all_placeholders_sharded(self) -> Dict[str, int]:
        """
        Perform bulk resolution using label-sharded index approach.
        
        Suitable for massive repositories (>5M definitions). Creates SymIndex
        nodes and resolves using node IDs rather than full entity scans.
        
        Returns:
            Dictionary with resolution statistics
        """
        # First, ensure SymIndex nodes exist
        self._ensure_sym_index_nodes()
        
        # Process in batches to avoid long-running transactions
        batch_size = 5000
        total_resolved_calls = 0
        total_resolved_imports = 0
        
        # Resolve call sites using SymIndex for lookup
        while True:
            call_site_query = f"""
            MATCH (cs:CallSite)
            WHERE NOT EXISTS((cs)-[:RESOLVES_TO]->())
            WITH cs LIMIT {batch_size}
            MATCH (si:SymIndex {{name: cs.call_name}})
            WITH cs, si, 
                 CASE WHEN si.file_id = cs.caller_file_id THEN 1.0 ELSE 0.7 END as score
            ORDER BY cs.id, score DESC
            WITH cs, collect(si)[0] as best_si, collect(score)[0] as best_score
            MATCH (f) WHERE id(f) = best_si.target_id
            MERGE (cs)-[r:RESOLVES_TO]->(f)
            SET r.score = best_score, r.timestamp = timestamp()
            RETURN count(r) as resolved_calls
            """
            
            call_result = self.neo4j_tool.execute_cypher(call_site_query)
            resolved_calls = call_result[0]["resolved_calls"] if call_result else 0
            total_resolved_calls += resolved_calls
            
            if resolved_calls == 0:
                break
                
            self.logger.info(f"Resolved {resolved_calls} call sites in this batch using SymIndex")
        
        # Resolve import sites using SymIndex for class lookups
        while True:
            import_site_query = f"""
            MATCH (is:ImportSite)
            WHERE NOT EXISTS((is)-[:RESOLVES_TO]->())
            WITH is LIMIT {batch_size}
            MATCH (si:SymIndex {{name: is.import_name, entity_type: 'Class'}})
            MATCH (c:Class) WHERE id(c) = si.target_id
            MERGE (is)-[r:RESOLVES_TO]->(c)
            SET r.score = 1.0, r.timestamp = timestamp()
            RETURN count(r) as resolved_imports
            """
            
            import_result = self.neo4j_tool.execute_cypher(import_site_query)
            resolved_imports = import_result[0]["resolved_imports"] if import_result else 0
            total_resolved_imports += resolved_imports
            
            if resolved_imports == 0:
                break
                
            self.logger.info(f"Resolved {resolved_imports} import sites in this batch using SymIndex")
        
        # Update graph statistics
        self.graph_stats["resolved_calls"] += total_resolved_calls
        self.graph_stats["resolved_imports"] += total_resolved_imports
        
        return {
            "resolved_calls": total_resolved_calls,
            "resolved_imports": total_resolved_imports
        }
    
    def _process_ast_with_composite(self, ast_data: Dict[str, Any], repository: str,
                               repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Process an AST using the Composite Pattern and Visitor Pattern.
        
        Args:
            ast_data: AST data dictionary
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract basic info
            file_path = ast_data.get("file_path", "")
            language = ast_data.get("language", "unknown")
            
            if not file_path:
                return {
                    "status": "error",
                    "error": "Missing file path in AST data"
                }
            
            # Create AST composite structure
            try:
                ast_root = ASTComposite.create_from_dict(ast_data)
            except ValueError as e:
                return {
                    "status": "error",
                    "error": f"Invalid AST structure: {str(e)}",
                    "file_path": file_path
                }
            
            # Create file node
            file_id = self._create_file_node(
                file_path=file_path,
                language=language,
                repository=repository,
                repository_url=repository_url,
                commit=commit,
                branch=branch
            )
            
            if not file_id:
                return {
                    "status": "error",
                    "error": "Failed to create file node",
                    "file_path": file_path
                }
            
            # Process functions with visitor
            function_visitor = FunctionVisitor()
            ast_root.accept(function_visitor)
            functions = function_visitor.get_result()
            
            # Create function and class nodes
            class_nodes = {}
            function_nodes = []
            
            for func in functions:
                # Check if it's a method in a class
                if func.get("is_method") and func.get("class_name"):
                    class_name = func.get("class_name")
                    class_id = func.get("class_id")
                    
                    # Create class node if not already created
                    if class_id not in class_nodes:
                        class_nodes[class_id] = {
                            "id": class_id,
                            "name": class_name,
                            "file_id": file_id,
                            "repository": repository,
                            "type": "Class"
                        }
                    
                    # Add method to the class
                    method_id = hashlib.md5(
                        f"{repository}:{file_id}:{class_name}.{func.get('name')}".encode()
                    ).hexdigest()
                    
                    function_nodes.append({
                        "id": method_id,
                        "name": func.get("name"),
                        "file_id": file_id,
                        "class_id": class_id,
                        "is_method": True,
                        "repository": repository
                    })
                else:
                    # Regular function
                    function_id = hashlib.md5(
                        f"{repository}:{file_id}:{func.get('name')}".encode()
                    ).hexdigest()
                    
                    function_nodes.append({
                        "id": function_id,
                        "name": func.get("name"),
                        "file_id": file_id,
                        "is_method": False,
                        "repository": repository
                    })
            
            # Create class nodes
            if class_nodes:
                self._batch_create_nodes("Class", list(class_nodes.values()))
            
            # Create function nodes
            if function_nodes:
                self._batch_create_nodes("Function", function_nodes)
            
            # Process calls with visitor
            if self.create_placeholders:
                # Use our direct extraction methods which include repository parameter
                call_sites = self._extract_call_sites(
                    ast_root=ast_root,
                    file_id=file_id,
                    repository=repository
                )
                
                import_sites = self._extract_import_sites(
                    ast_root=ast_root,
                    file_id=file_id,
                    repository=repository
                )
            else:
                call_sites = []
                import_sites = []
            
            # Update visitor calls counter
            self.graph_stats["visitor_calls"] += 1
            
            # Success result
            entity_count = len(function_nodes) + len(class_nodes)
            
            return {
                "status": "success",
                "file_id": file_id,
                "entity_count": entity_count,
                "relationship_count": 0,  # Could calculate actual relationships
                "call_sites": len(call_sites),
                "import_sites": len(import_sites)
            }
            
        except Exception as e:
            self.logger.exception(f"Error processing AST with composite pattern for {file_path}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path
            }
    
    def _process_ast(self, ast_data: Dict[str, Any], repository: str,
                   repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Process a single AST and build corresponding graph with placeholders.
        
        This method implements the Strategy Pattern to select the most
        appropriate processing strategy based on AST characteristics.
        
        Args:
            ast_data: AST data dictionary
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            Dictionary with processing results
        """
        # Extract basic file info for error handling
        file_path = ast_data.get("file_path", "")
        language = ast_data.get("language", "unknown")
        
        # Create file node first (common to all strategies)
        file_id = self._create_file_node(
            file_path=file_path,
            language=language,
            repository=repository,
            repository_url=repository_url,
            commit=commit,
            branch=branch
        )
        
        if not file_id:
            return {
                "status": "error",
                "error": "Failed to create file node",
                "file_path": file_path
            }
        
        try:
            # Use the Strategy Pattern if enabled
            if self.use_strategy_pattern:
                # Create processing context
                context = {
                    "repository": repository,
                    "repository_url": repository_url,
                    "commit": commit,
                    "branch": branch,
                    "file_id": file_id,
                    "create_placeholders": self.create_placeholders,
                    "immediate_resolution": self.immediate_resolution,
                    "config": self.strategy_config
                }
                
                # Explicitly set strategy if configured
                if self.default_processing_strategy:
                    context["processing_strategy"] = self.default_processing_strategy
                
                # Use the factory to create the appropriate strategy
                strategy = ASTProcessingStrategyFactory.create_strategy(ast_data, context)
                
                # Process the AST using the selected strategy
                self.logger.info(f"Processing AST with strategy: {strategy.__class__.__name__}")
                strategy_result = strategy.process_ast(ast_data, context)
                self.graph_stats["strategy_calls"] += 1
                
                # Handle strategy result
                if strategy_result.get("status") == "success":
                    # Extract results from strategy processing
                    functions = strategy_result.get("functions", [])
                    classes = strategy_result.get("classes", [])
                    call_sites = strategy_result.get("call_sites", [])
                    import_sites = strategy_result.get("import_sites", [])
                    
                    # Create function and class nodes
                    self._process_functions(functions, file_id, repository)
                    self._process_classes(classes, file_id, repository)
                    
                    # Create call site and import site nodes if placeholders are enabled
                    if self.create_placeholders:
                        self._process_call_sites(call_sites, file_id, repository)
                        self._process_import_sites(import_sites, file_id, repository)
                    
                    # Update stats
                    self.graph_stats["files"] += 1
                    self.graph_stats["functions"] += len(functions)
                    self.graph_stats["call_sites"] += len(call_sites)
                    self.graph_stats["import_sites"] += len(import_sites)
                    
                    return {
                        "status": "success",
                        "file_id": file_id,
                        "entity_count": len(functions) + len(classes),
                        "relationship_count": 0,  # Would be calculated in a real implementation
                        "call_sites": len(call_sites),
                        "import_sites": len(import_sites),
                        "strategy": strategy_result.get("strategy")
                    }
                else:
                    # Strategy processing failed, log the error
                    error = strategy_result.get("error", "Unknown error in strategy processing")
                    self.logger.warning(f"Strategy processing failed: {error}")
                    # Fall back to legacy approaches
                
            # Legacy fallback approaches if strategy pattern is disabled or failed
            
            # Use iterator pattern if enabled and appropriate
            if self.use_iterator_pattern:
                # Check if we should use streaming or dict iterator based on size
                if ast_data.get("file_size", 0) > 5000000:  # For very large files (>5MB)
                    try:
                        # Use file-based streaming if AST is available as file
                        ast_file_path = ast_data.get("file_path_ast")
                        if ast_file_path and os.path.exists(ast_file_path):
                            return self._process_ast_with_streaming_iterator(
                                ast_file_path=ast_file_path,
                                file_path=file_path,
                                language=language,
                                repository=repository,
                                repository_url=repository_url,
                                commit=commit,
                                branch=branch
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to process AST with streaming iterator, falling back to dict iterator: {str(e)}"
                        )
                
                # Use dict iterator for moderately large files (>500KB)
                if ast_data.get("file_size", 0) > 500000:
                    try:
                        return self._process_ast_with_iterator(
                            ast_data=ast_data,
                            repository=repository,
                            repository_url=repository_url,
                            commit=commit,
                            branch=branch
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to process AST with iterator pattern, falling back to composite pattern: {str(e)}"
                        )
            
            # Use composite pattern if enabled and appropriate
            if self.use_composite_pattern:
                try:
                    return self._process_ast_with_composite(
                        ast_data=ast_data,
                        repository=repository,
                        repository_url=repository_url,
                        commit=commit,
                        branch=branch
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to process AST with composite pattern, falling back to standard processing: {str(e)}"
                    )
            
            # Standard processing as fallback
            try:
                # Handle different AST formats (tree-sitter vs native)
                if "root" in ast_data:
                    ast_root = ast_data.get("root", {})
                    self.logger.debug("Using native AST format with 'root' field")
                    ast_format = "native"
                else:
                    # For tree-sitter ASTs, check if it has the expected structure
                    if "type" in ast_data and "children" in ast_data:
                        ast_root = ast_data  # The AST itself is the root
                        self.logger.debug("Using tree-sitter AST format where the AST itself is the root")
                        ast_format = "tree-sitter"
                    else:
                        ast_root = {}
                        ast_format = "unknown"
                
                if not ast_root or not ast_root.get("type"):
                    error_msg = "Missing AST root"
                    if file_path:
                        error_msg += f" for file: {file_path}"
                    return {
                        "status": "error",
                        "error": error_msg,
                        "file_path": file_path
                    }
                
                # Add AST format information for downstream processing
                ast_data["_ast_format"] = ast_format
                ast_root["_ast_format"] = ast_format
                
                # Add repository information for ID generation
                ast_data["repository"] = repository
                ast_root["repository"] = repository
                
                # Extract and create entities (classes, functions, etc.)
                entity_count = self._extract_entities(
                    ast_root=ast_root,
                    file_id=file_id,
                    file_path=file_path,
                    language=language
                )
                
                # Create relationships between entities
                relationship_count = self._create_relationships(
                    ast_root=ast_root,
                    file_id=file_id
                )
                
                # Extract and create call sites
                call_sites = []
                import_sites = []
                
                if self.create_placeholders:
                    call_sites = self._extract_call_sites(
                        ast_root=ast_root,
                        file_id=file_id
                    )
                    
                    import_sites = self._extract_import_sites(
                        ast_root=ast_root,
                        file_id=file_id
                    )
                
                # Update stats
                self.graph_stats["files"] += 1
                
                return {
                    "status": "success",
                    "file_id": file_id,
                    "entity_count": entity_count,
                    "relationship_count": relationship_count,
                    "call_sites": len(call_sites),
                    "import_sites": len(import_sites),
                    "strategy": "standard"
                }
                
            except Exception as e:
                self.logger.exception(f"Error in standard AST processing for {file_path}: {str(e)}")
                return {
                    "status": "error",
                    "error": str(e),
                    "file_path": file_path
                }
                
        except Exception as e:
            self.logger.exception(f"Error processing AST for {file_path}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path
            }
            
    def _process_functions(self, functions: List[Dict[str, Any]], file_id: str, repository: str) -> None:
        """
        Process function data from a strategy's result.
        
        Args:
            functions: List of function data dictionaries
            file_id: ID of the file
            repository: Repository name
        """
        if not functions:
            return
            
        # Extract class info from functions that are methods
        class_nodes = {}
        function_nodes = []
        
        for func in functions:
            # Add to function nodes
            function_nodes.append(func)
            
            # If it's a method, add the class
            if func.get("is_method") and func.get("class_id") and func.get("class_name"):
                class_id = func["class_id"]
                if class_id not in class_nodes:
                    class_nodes[class_id] = {
                        "id": class_id,
                        "name": func["class_name"],
                        "file_id": file_id,
                        "repository": repository,
                        "type": "Class"
                    }
        
        # Create class nodes
        if class_nodes:
            self._batch_create_nodes("Class", list(class_nodes.values()))
        
        # Create function nodes
        if function_nodes:
            self._batch_create_nodes("Function", function_nodes)
    
    def _process_classes(self, classes: List[Dict[str, Any]], file_id: str, repository: str) -> None:
        """
        Process class data from a strategy's result.
        
        Args:
            classes: List of class data dictionaries
            file_id: ID of the file
            repository: Repository name
        """
        if not classes:
            return
            
        # Create class nodes
        self._batch_create_nodes("Class", classes)
        
        # Update stats
        self.graph_stats["classes"] += len(classes)
    
    def _process_call_sites(self, call_sites: List[Dict[str, Any]], file_id: str, repository: str) -> None:
        """
        Process call site data from a strategy's result.
        
        Args:
            call_sites: List of call site data dictionaries
            file_id: ID of the file
            repository: Repository name
        """
        if not call_sites:
            return
            
        for call_info in call_sites:
            # Extract position info
            position = call_info.get("position", {})
            start_line = position.get("start_line", 0)
            start_col = position.get("start_column", 0)
            end_line = position.get("end_line", 0)
            end_col = position.get("end_column", 0)
            
            # Generate call ID if not provided
            call_id = call_info.get("id")
            if not call_id:
                call_id = hashlib.md5(
                    f"{repository}:{file_id}:{start_line}:{start_col}:{call_info.get('name', '')}".encode()
                ).hexdigest()
            
            # Create call site node
            self.neo4j_tool.create_call_site_node(
                call_id=call_id,
                caller_file_id=file_id,
                caller_function_id=call_info.get("function_id"),
                caller_class_id=call_info.get("class_id"),
                call_name=call_info.get("name", ""),
                call_module=call_info.get("module"),
                start_line=start_line,
                start_col=start_col,
                end_line=end_line,
                end_col=end_col,
                is_attribute_call=call_info.get("is_attribute", False)
            )
            
            # Attempt immediate resolution if configured
            if self.immediate_resolution:
                self._resolve_call_site(call_id, call_info, file_id)
    
    def _process_import_sites(self, import_sites: List[Dict[str, Any]], file_id: str, repository: str) -> None:
        """
        Process import site data from a strategy's result.
        
        Args:
            import_sites: List of import site data dictionaries
            file_id: ID of the file
            repository: Repository name
        """
        if not import_sites:
            return
            
        for import_info in import_sites:
            # Extract position info
            position = import_info.get("position", {})
            start_line = position.get("start_line", 0)
            end_line = position.get("end_line", 0)
            
            # Generate import ID if not provided
            import_id = import_info.get("id")
            if not import_id:
                import_prefix = "import" if not import_info.get("is_from_import") else "import_from"
                import_name = import_info.get("name", "")
                module_part = f":{import_info.get('module', '')}" if import_info.get("is_from_import") else ""
                
                import_id = hashlib.md5(
                    f"{repository}:{file_id}:{import_prefix}:{start_line}{module_part}.{import_name}".encode()
                ).hexdigest()
            
            # Create import site node
            self.neo4j_tool.create_import_site_node(
                import_id=import_id,
                file_id=file_id,
                import_name=import_info.get("name", ""),
                module_name=import_info.get("module"),
                alias=import_info.get("alias", ""),
                is_from_import=import_info.get("is_from_import", False),
                start_line=start_line,
                end_line=end_line
            )
    
    def _process_ast_with_iterator(self, ast_data: Dict[str, Any], repository: str,
                          repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Process an AST using the Iterator Pattern for memory-efficient traversal.
        
        This method is optimized for large ASTs as it processes the tree incrementally
        without loading the entire structure into memory at once.
        
        Args:
            ast_data: AST data dictionary
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract basic info
            file_path = ast_data.get("file_path", "")
            language = ast_data.get("language", "unknown")
            
            if not file_path:
                return {
                    "status": "error",
                    "error": "Missing file path in AST data"
                }
            
            # Create file node
            file_id = self._create_file_node(
                file_path=file_path,
                language=language,
                repository=repository,
                repository_url=repository_url,
                commit=commit,
                branch=branch
            )
            
            if not file_id:
                return {
                    "status": "error",
                    "error": "Failed to create file node",
                    "file_path": file_path
                }
            
            # Create AST iterator
            ast_iterator = ASTIteratorFactory.create_iterator(
                ast_data=ast_data,
                iterator_type="dict",
                traverse_mode="depth_first"
            )
            
            # Process functions
            function_nodes = []
            class_nodes = {}
            
            # Get all function nodes using the iterator
            for func_node in get_functions(ast_iterator):
                # Extract function info
                func_name = ""
                is_method = False
                class_name = None
                class_id = None
                
                # Extract name based on AST format
                if func_node.get("type") in ["FunctionDef", "Function", "function_definition"]:
                    # Get function name
                    if "attributes" in func_node and "name" in func_node["attributes"]:
                        func_name = func_node["attributes"]["name"]
                    elif "text" in func_node:
                        func_name = func_node["text"]
                    
                    # Determine if it's a method by looking at its context
                    parent_context = self._get_parent_context(func_node)
                    if parent_context and parent_context.get("type") in ["ClassDef", "Class", "class_definition"]:
                        is_method = True
                        class_name = self._get_node_name(parent_context)
                        if class_name:
                            class_id = hashlib.md5(
                                f"{repository}:{file_id}:{class_name}".encode()
                            ).hexdigest()
                            
                            # Add class to the collection if not already present
                            if class_id not in class_nodes:
                                class_nodes[class_id] = {
                                    "id": class_id,
                                    "name": class_name,
                                    "file_id": file_id,
                                    "repository": repository,
                                    "type": "Class"
                                }
                
                # Skip if we couldn't determine the name
                if not func_name:
                    continue
                
                # Generate function ID
                if is_method and class_name:
                    func_id = hashlib.md5(
                        f"{repository}:{file_id}:{class_name}.{func_name}".encode()
                    ).hexdigest()
                else:
                    func_id = hashlib.md5(
                        f"{repository}:{file_id}:{func_name}".encode()
                    ).hexdigest()
                
                # Create function node data
                function_nodes.append({
                    "id": func_id,
                    "name": func_name,
                    "file_id": file_id,
                    "class_id": class_id,
                    "is_method": is_method,
                    "repository": repository
                })
            
            # Create class nodes
            if class_nodes:
                self._batch_create_nodes("Class", list(class_nodes.values()))
            
            # Create function nodes
            if function_nodes:
                self._batch_create_nodes("Function", function_nodes)
            
            # Process call sites if enabled
            call_sites = []
            if self.create_placeholders:
                # Reset iterator for call site processing
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_data,
                    iterator_type="dict",
                    traverse_mode="depth_first"
                )
                
                # Find all call nodes
                for call_node in get_calls(ast_iterator):
                    # Extract call info
                    call_info = self._extract_call_info_from_node(call_node, repository)
                    if call_info:
                        # Generate a unique ID for the call site
                        position = call_info.get("position", {})
                        start_line = position.get("start_line", 0)
                        start_col = position.get("start_column", 0)
                        
                        call_id = hashlib.md5(
                            f"{repository}:{file_id}:{start_line}:{start_col}:{call_info.get('name', '')}".encode()
                        ).hexdigest()
                        
                        # Create call site node
                        self.neo4j_tool.create_call_site_node(
                            call_id=call_id,
                            caller_file_id=file_id,
                            caller_function_id=call_info.get("function_id"),
                            caller_class_id=call_info.get("class_id"),
                            call_name=call_info.get("name", ""),
                            call_module=call_info.get("module"),
                            start_line=start_line,
                            start_col=start_col,
                            end_line=position.get("end_line", 0),
                            end_col=position.get("end_column", 0),
                            is_attribute_call=call_info.get("is_attribute", False)
                        )
                        
                        call_sites.append(call_id)
                        self.graph_stats["call_sites"] += 1
                        
                        # Attempt immediate resolution if configured
                        if self.immediate_resolution:
                            self._resolve_call_site(call_id, call_info, file_id)
            
            # Process import sites if enabled
            import_sites = []
            if self.create_placeholders:
                # Reset iterator for import processing
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_data,
                    iterator_type="dict",
                    traverse_mode="depth_first"
                )
                
                # Find all import nodes
                for import_node in get_imports(ast_iterator):
                    # Extract import info
                    import_info = self._extract_import_info_from_node(import_node, repository)
                    if import_info:
                        # Generate a unique ID for the import site
                        position = import_info.get("position", {})
                        start_line = position.get("start_line", 0)
                        
                        import_prefix = "import" if not import_info.get("is_from_import") else "import_from"
                        import_name = import_info.get("name", "")
                        module_part = f":{import_info.get('module', '')}" if import_info.get("is_from_import") else ""
                        
                        import_id = hashlib.md5(
                            f"{repository}:{file_id}:{import_prefix}:{start_line}{module_part}.{import_name}".encode()
                        ).hexdigest()
                        
                        # Create import site node
                        self.neo4j_tool.create_import_site_node(
                            import_id=import_id,
                            file_id=file_id,
                            import_name=import_name,
                            module_name=import_info.get("module"),
                            alias=import_info.get("alias", ""),
                            is_from_import=import_info.get("is_from_import", False),
                            start_line=start_line,
                            end_line=position.get("end_line", 0)
                        )
                        
                        import_sites.append(import_id)
                        self.graph_stats["import_sites"] += 1
            
            # Update iterator calls counter
            self.graph_stats["iterator_calls"] += 1
            
            # Success result
            entity_count = len(function_nodes) + len(class_nodes)
            
            return {
                "status": "success",
                "file_id": file_id,
                "entity_count": entity_count,
                "relationship_count": 0,  # Could calculate actual relationships
                "call_sites": len(call_sites),
                "import_sites": len(import_sites)
            }
            
        except Exception as e:
            self.logger.exception(f"Error processing AST with iterator pattern for {ast_data.get('file_path', 'unknown')}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": ast_data.get("file_path", "unknown")
            }
    
    def _get_node_name(self, node: Dict[str, Any]) -> str:
        """
        Extract name from a node based on AST format.
        
        Args:
            node: AST node
            
        Returns:
            Name of the node or empty string
        """
        # Check attributes dictionary
        if "attributes" in node and isinstance(node["attributes"], dict):
            if "name" in node["attributes"]:
                return node["attributes"]["name"]
            elif "id" in node["attributes"]:
                return node["attributes"]["id"]
        
        # Check direct text field (tree-sitter format)
        if "text" in node:
            return node["text"]
        
        # Check type-specific child nodes
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                if isinstance(child, dict):
                    # Name node (Python AST)
                    if child.get("type") == "Name":
                        if "attributes" in child and "id" in child["attributes"]:
                            return child["attributes"]["id"]
                        elif "text" in child:
                            return child["text"]
                    
                    # Identifier node (tree-sitter)
                    elif child.get("type") == "identifier":
                        if "text" in child:
                            return child["text"]
        
        return ""
    
    def _get_parent_context(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get parent context from a node (workaround for Iterator pattern).
        
        This is a simplified implementation since the Iterator pattern doesn't
        track parent-child relationships explicitly.
        
        Args:
            node: AST node
            
        Returns:
            Parent node or None
        """
        # This is challenging with the Iterator pattern since it doesn't track parent nodes
        # In a real implementation, you would need to build context during iteration
        # Here we'll use a heuristic approach looking at context information in the node
        
        if "parent_type" in node:
            # If parent type info was explicitly added
            return {"type": node["parent_type"]}
            
        # For future improvement:
        # A more robust implementation would involve storing context during iteration
        return None
    
    def _extract_call_info_from_node(self, call_node: Dict[str, Any], repository: str) -> Optional[Dict[str, Any]]:
        """
        Extract call information from a node.
        
        Args:
            call_node: Call AST node
            repository: Repository name
            
        Returns:
            Dictionary with call information or None
        """
        if not call_node or not isinstance(call_node, dict):
            return None
            
        call_info = {
            "name": "",
            "is_attribute": False,
            "position": {}
        }
        
        # Get position info
        if "start_position" in call_node and "end_position" in call_node:
            # Native AST format
            start_pos = call_node.get("start_position", {})
            end_pos = call_node.get("end_position", {})
            
            call_info["position"] = {
                "start_line": start_pos.get("row", 0),
                "start_column": start_pos.get("column", 0),
                "end_line": end_pos.get("row", 0),
                "end_column": end_pos.get("column", 0)
            }
        elif "start_point" in call_node and "end_point" in call_node:
            # Tree-sitter format
            start_point = call_node.get("start_point", {})
            end_point = call_node.get("end_point", {})
            
            if isinstance(start_point, dict):
                start_line = start_point.get("row", 0)
                start_col = start_point.get("column", 0)
            else:
                # Handle case where it might be a tuple instead of dict
                start_line = start_point[0] if isinstance(start_point, (list, tuple)) and len(start_point) > 0 else 0
                start_col = start_point[1] if isinstance(start_point, (list, tuple)) and len(start_point) > 1 else 0
            
            if isinstance(end_point, dict):
                end_line = end_point.get("row", 0)
                end_col = end_point.get("column", 0)
            else:
                # Handle case where it might be a tuple instead of dict
                end_line = end_point[0] if isinstance(end_point, (list, tuple)) and len(end_point) > 0 else 0
                end_col = end_point[1] if isinstance(end_point, (list, tuple)) and len(end_point) > 1 else 0
                
            call_info["position"] = {
                "start_line": start_line,
                "start_column": start_col,
                "end_line": end_line,
                "end_column": end_col
            }
        
        # Process function info based on AST format
        if "children" in call_node and len(call_node["children"]) > 0:
            # Tree-sitter format likely
            func_node = call_node["children"][0]
            
            if func_node.get("type") == "identifier":
                # Simple function call: function_name()
                call_info["name"] = func_node.get("text", "")
                call_info["is_attribute"] = False
                
            elif func_node.get("type") == "attribute":
                # Method call: object.method()
                call_info["is_attribute"] = True
                
                # With tree-sitter, attribute nodes have children
                if len(func_node.get("children", [])) >= 3:
                    # The children structure is usually: [object, ".", method]
                    obj_node = func_node["children"][0]
                    method_node = func_node["children"][2]
                    
                    if method_node.get("type") == "identifier":
                        call_info["name"] = method_node.get("text", "")
                        
                        if obj_node.get("type") == "identifier":
                            # Simple attribute: object.method()
                            call_info["module"] = obj_node.get("text", "")
        
        elif "attributes" in call_node and "func" in call_node["attributes"]:
            # Native AST format
            func = call_node["attributes"]["func"]
            
            if func.get("type") == "Name":
                # Simple function call: function_name()
                call_info["name"] = func.get("attributes", {}).get("id", "")
                call_info["is_attribute"] = False
                
            elif func.get("type") == "Attribute":
                # Method call: object.method()
                call_info["is_attribute"] = True
                
                attrs = func.get("attributes", {})
                call_info["name"] = attrs.get("attr", "")
                value = attrs.get("value", {})
                
                if value.get("type") == "Name":
                    # Simple attribute: object.method()
                    call_info["module"] = value.get("attributes", {}).get("id", "")
        
        # If we couldn't determine the name, return None
        if not call_info["name"]:
            return None
            
        return call_info
    
    def _process_ast_with_streaming_iterator(self, ast_file_path: str, file_path: str, language: str,
                                    repository: str, repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Process an AST using the StreamingASTIterator for handling extremely large ASTs.
        
        This method processes AST data directly from a file without loading the entire
        structure into memory, making it suitable for very large ASTs (>5MB).
        
        Args:
            ast_file_path: Path to the AST file
            file_path: Path to the original source file
            language: Programming language
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Create file node
            file_id = self._create_file_node(
                file_path=file_path,
                language=language,
                repository=repository,
                repository_url=repository_url,
                commit=commit,
                branch=branch
            )
            
            if not file_id:
                return {
                    "status": "error",
                    "error": "Failed to create file node",
                    "file_path": file_path
                }
            
            # Create streaming AST iterator
            ast_iterator = ASTIteratorFactory.create_iterator(
                ast_data=ast_file_path,
                iterator_type="streaming",
                chunk_size=1000  # Process 1000 lines at a time
            )
            
            # Process functions
            function_nodes = []
            class_nodes = {}
            call_sites = []
            import_sites = []
            
            # Track counts for statistics
            function_count = 0
            call_site_count = 0
            import_site_count = 0
            
            # Process functions (first pass)
            for func_node in get_functions(ast_iterator):
                function_info = self._extract_function_info_from_node(func_node, repository, file_id)
                if function_info:
                    function_count += 1
                    
                    # Add to function nodes
                    function_nodes.append(function_info)
                    
                    # If it's a method, add the class
                    if function_info.get("is_method") and function_info.get("class_id"):
                        class_id = function_info["class_id"]
                        if class_id not in class_nodes:
                            class_nodes[class_id] = {
                                "id": class_id,
                                "name": function_info["class_name"],
                                "file_id": file_id,
                                "repository": repository,
                                "type": "Class"
                            }
                    
                    # Batch create nodes periodically
                    if function_count % 100 == 0:
                        # Create accumulated nodes
                        if function_nodes:
                            self._batch_create_nodes("Function", function_nodes)
                            function_nodes = []
                            
                        if class_nodes:
                            self._batch_create_nodes("Class", list(class_nodes.values()))
                            class_nodes = {}
            
            # Create any remaining function and class nodes
            if function_nodes:
                self._batch_create_nodes("Function", function_nodes)
            
            if class_nodes:
                self._batch_create_nodes("Class", list(class_nodes.values()))
            
            # Process call sites (second pass)
            if self.create_placeholders:
                # Reset iterator for call site processing
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_file_path,
                    iterator_type="streaming",
                    chunk_size=1000
                )
                
                # Find all call nodes
                for call_node in get_calls(ast_iterator):
                    call_info = self._extract_call_info_from_node(call_node, repository)
                    if call_info:
                        call_site_count += 1
                        
                        # Generate a unique ID for the call site
                        position = call_info.get("position", {})
                        start_line = position.get("start_line", 0)
                        start_col = position.get("start_column", 0)
                        
                        call_id = hashlib.md5(
                            f"{repository}:{file_id}:{start_line}:{start_col}:{call_info.get('name', '')}".encode()
                        ).hexdigest()
                        
                        # Create call site node
                        self.neo4j_tool.create_call_site_node(
                            call_id=call_id,
                            caller_file_id=file_id,
                            caller_function_id=call_info.get("function_id"),
                            caller_class_id=call_info.get("class_id"),
                            call_name=call_info.get("name", ""),
                            call_module=call_info.get("module"),
                            start_line=start_line,
                            start_col=start_col,
                            end_line=position.get("end_line", 0),
                            end_col=position.get("end_column", 0),
                            is_attribute_call=call_info.get("is_attribute", False)
                        )
                        
                        call_sites.append(call_id)
                        
                        # Attempt immediate resolution if configured
                        if self.immediate_resolution and call_site_count % 20 == 0:
                            self._resolve_call_site(call_id, call_info, file_id)
                
                # Process import sites (third pass)
                ast_iterator = ASTIteratorFactory.create_iterator(
                    ast_data=ast_file_path,
                    iterator_type="streaming",
                    chunk_size=1000
                )
                
                # Find all import nodes
                for import_node in get_imports(ast_iterator):
                    import_info = self._extract_import_info_from_node(import_node, repository)
                    if import_info:
                        import_site_count += 1
                        
                        # Generate a unique ID for the import site
                        position = import_info.get("position", {})
                        start_line = position.get("start_line", 0)
                        
                        import_prefix = "import" if not import_info.get("is_from_import") else "import_from"
                        import_name = import_info.get("name", "")
                        module_part = f":{import_info.get('module', '')}" if import_info.get("is_from_import") else ""
                        
                        import_id = hashlib.md5(
                            f"{repository}:{file_id}:{import_prefix}:{start_line}{module_part}.{import_name}".encode()
                        ).hexdigest()
                        
                        # Create import site node
                        self.neo4j_tool.create_import_site_node(
                            import_id=import_id,
                            file_id=file_id,
                            import_name=import_name,
                            module_name=import_info.get("module"),
                            alias=import_info.get("alias", ""),
                            is_from_import=import_info.get("is_from_import", False),
                            start_line=start_line,
                            end_line=position.get("end_line", 0)
                        )
                        
                        import_sites.append(import_id)
            
            # Update statistics
            self.graph_stats["files"] += 1
            self.graph_stats["call_sites"] += call_site_count
            self.graph_stats["import_sites"] += import_site_count
            self.graph_stats["iterator_calls"] += 1
            
            # Success result
            return {
                "status": "success",
                "file_id": file_id,
                "entity_count": function_count + len(class_nodes),
                "relationship_count": 0,
                "call_sites": call_site_count,
                "import_sites": import_site_count,
                "streaming": True
            }
            
        except Exception as e:
            self.logger.exception(f"Error processing AST with streaming iterator for {file_path}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file_path": file_path
            }
    
    def _extract_function_info_from_node(self, func_node: Dict[str, Any], repository: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract function information from a node.
        
        Args:
            func_node: Function AST node
            repository: Repository name
            file_id: File ID
            
        Returns:
            Dictionary with function information or None
        """
        if not func_node or not isinstance(func_node, dict):
            return None
            
        # Get function name
        func_name = self._get_node_name(func_node)
        if not func_name:
            return None
            
        # Determine if it's a method
        is_method = False
        class_name = None
        class_id = None
        
        # Check parent context for class
        parent_context = self._get_parent_context(func_node)
        if parent_context and parent_context.get("type") in ["ClassDef", "Class", "class_definition"]:
            is_method = True
            class_name = self._get_node_name(parent_context)
            if class_name:
                class_id = hashlib.md5(
                    f"{repository}:{file_id}:{class_name}".encode()
                ).hexdigest()
        
        # Generate function ID
        if is_method and class_name:
            func_id = hashlib.md5(
                f"{repository}:{file_id}:{class_name}.{func_name}".encode()
            ).hexdigest()
        else:
            func_id = hashlib.md5(
                f"{repository}:{file_id}:{func_name}".encode()
            ).hexdigest()
        
        # Create function information
        function_info = {
            "id": func_id,
            "name": func_name,
            "file_id": file_id,
            "class_id": class_id,
            "class_name": class_name,
            "is_method": is_method,
            "repository": repository
        }
        
        return function_info
    
    def _extract_import_info_from_node(self, import_node: Dict[str, Any], repository: str) -> Optional[Dict[str, Any]]:
        """
        Extract import information from a node.
        
        Args:
            import_node: Import AST node
            repository: Repository name
            
        Returns:
            Dictionary with import information or None
        """
        if not import_node or not isinstance(import_node, dict):
            return None
            
        import_info = {
            "name": "",
            "is_from_import": False,
            "position": {}
        }
        
        # Get position info
        if "start_position" in import_node and "end_position" in import_node:
            # Native AST format
            start_pos = import_node.get("start_position", {})
            end_pos = import_node.get("end_position", {})
            
            import_info["position"] = {
                "start_line": start_pos.get("row", 0),
                "start_column": start_pos.get("column", 0),
                "end_line": end_pos.get("row", 0),
                "end_column": end_pos.get("column", 0)
            }
        elif "start_point" in import_node and "end_point" in import_node:
            # Tree-sitter format
            start_point = import_node.get("start_point", {})
            end_point = import_node.get("end_point", {})
            
            if isinstance(start_point, dict):
                start_line = start_point.get("row", 0)
                start_col = start_point.get("column", 0)
            else:
                # Handle case where it might be a tuple instead of dict
                start_line = start_point[0] if isinstance(start_point, (list, tuple)) and len(start_point) > 0 else 0
                start_col = start_point[1] if isinstance(start_point, (list, tuple)) and len(start_point) > 1 else 0
            
            if isinstance(end_point, dict):
                end_line = end_point.get("row", 0)
                end_col = end_point.get("column", 0)
            else:
                # Handle case where it might be a tuple instead of dict
                end_line = end_point[0] if isinstance(end_point, (list, tuple)) and len(end_point) > 0 else 0
                end_col = end_point[1] if isinstance(end_point, (list, tuple)) and len(end_point) > 1 else 0
                
            import_info["position"] = {
                "start_line": start_line,
                "start_column": start_col,
                "end_line": end_line,
                "end_column": end_col
            }
        
        # Determine if it's an import-from statement
        if import_node.get("type") in ["ImportFrom", "import_from_statement"]:
            import_info["is_from_import"] = True
        
        # Process import information based on AST format
        if "attributes" in import_node:
            # Native AST format
            if import_info["is_from_import"]:
                # From-import: from module import name
                import_info["module"] = import_node["attributes"].get("module", "")
                
                # Get first name from names list
                names = import_node["attributes"].get("names", [])
                if names and isinstance(names, list) and len(names) > 0:
                    import_info["name"] = names[0].get("name", "")
                    import_info["alias"] = names[0].get("asname", "")
            else:
                # Direct import: import module
                names = import_node["attributes"].get("names", [])
                if names and isinstance(names, list) and len(names) > 0:
                    import_info["name"] = names[0].get("name", "")
                    import_info["alias"] = names[0].get("asname", "")
        
        elif "children" in import_node:
            # Tree-sitter format
            if import_info["is_from_import"]:
                # From-import: from module import name
                for child in import_node.get("children", []):
                    if child.get("type") == "dotted_name":
                        # Module name
                        module_parts = []
                        for part in child.get("children", []):
                            if part.get("type") == "identifier":
                                module_parts.append(part.get("text", ""))
                        import_info["module"] = ".".join(module_parts)
                    elif child.get("type") == "import_items":
                        # Imported names
                        for item in child.get("children", []):
                            if item.get("type") == "dotted_name" or item.get("type") == "identifier":
                                if item.get("type") == "identifier":
                                    import_info["name"] = item.get("text", "")
                                else:
                                    for name_part in item.get("children", []):
                                        if name_part.get("type") == "identifier":
                                            import_info["name"] = name_part.get("text", "")
                                            break
                                break
            else:
                # Direct import: import module
                for child in import_node.get("children", []):
                    if child.get("type") == "dotted_name":
                        # Module being imported
                        for part in child.get("children", []):
                            if part.get("type") == "identifier":
                                import_info["name"] = part.get("text", "")
                                break
                        break
        
        # If we couldn't determine the name, return None
        if not import_info["name"]:
            return None
            
        return import_info

    def _setup_observers(self) -> None:
        """Set up the indexing observers based on configuration."""
        if not self.use_observer_pattern:
            return
            
        # Get observer configuration
        observer_config = self.config.get("observer_config", {})
        
        # Add console observer if enabled
        if observer_config.get("console_observer", True):
            verbose = observer_config.get("console_verbose", False)
            console_observer = ConsoleIndexingObserver(verbose=verbose)
            self.observer_manager.add_observer(console_observer)
            
        # Add file observer if enabled
        if observer_config.get("file_observer", False):
            output_file = observer_config.get("file_observer_path", "indexing_events.log")
            file_observer = FileIndexingObserver(output_file=output_file)
            self.observer_manager.add_observer(file_observer)
            
        # Add statistics observer for tracking metrics
        self.stats_observer = StatisticsIndexingObserver()
        self.observer_manager.add_observer(self.stats_observer)
        
        # Add progress bar observer if enabled and in interactive mode
        if observer_config.get("progress_bar", True) and self._is_interactive():
            progress_observer = ProgressBarIndexingObserver()
            self.observer_manager.add_observer(progress_observer)
            
        self.logger.info(f"Set up {len(self.observer_manager.observers)} indexing observers")
    
    def _is_interactive(self) -> bool:
        """Check if running in an interactive terminal."""
        # Simple check for interactive terminal
        return hasattr(sys, 'ps1') or sys.stdout.isatty()
    
    def _notify_file_processed(self, file_path: str, file_id: str) -> None:
        """
        Notify observers that a file has been processed.
        
        Args:
            file_path: Path to the processed file
            file_id: ID of the processed file
        """
        if self.use_observer_pattern:
            event = self.observer_manager.create_file_processed_event(
                source=self.__class__.__name__,
                file_path=file_path,
                file_id=file_id
            )
            self.observer_manager.notify_observers(event)
    
    def _notify_error(self, error_message: str, details: Dict[str, Any] = None) -> None:
        """
        Notify observers of an error.
        
        Args:
            error_message: Error message
            details: Optional error details
        """
        if self.use_observer_pattern:
            event = self.observer_manager.create_error_event(
                source=self.__class__.__name__,
                error_message=error_message,
                details=details
            )
            self.observer_manager.notify_observers(event)
    
    def _notify_progress(self, percentage: float, message: str = "") -> None:
        """
        Notify observers of progress.
        
        Args:
            percentage: Progress percentage (0-100)
            message: Optional progress message
        """
        if self.use_observer_pattern:
            event = self.observer_manager.create_progress_event(
                source=self.__class__.__name__,
                percentage=percentage,
                message=message
            )
            self.observer_manager.notify_observers(event)
    
    def _batch_process_asts(self, asts: List[Dict[str, Any]], repository: str,
                             repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Process a batch of ASTs in parallel for efficient graph building.
        
        Args:
            asts: List of AST data dictionaries
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            Dictionary with batch processing results
        """
        self.logger.info(f"Batch processing {len(asts)} ASTs")
        
        # Notify observers of batch processing start
        if self.use_observer_pattern:
            stage_event = self.observer_manager.create_stage_started_event(
                source=self.__class__.__name__,
                stage_name="BatchProcessing"
            )
            self.observer_manager.notify_observers(stage_event)
            
            # Notify initial progress
            self._notify_progress(0.0, f"Starting batch processing of {len(asts)} ASTs")
        
        # Define processing function for each AST
        def process_ast_func(ast_data: Dict[str, Any]) -> Dict[str, Any]:
            result = self._process_ast(
                ast_data=ast_data,
                repository=repository,
                repository_url=repository_url,
                commit=commit,
                branch=branch
            )
            
            # Notify observers of file processing (in the worker thread/process)
            if self.use_observer_pattern and result.get("status") == "success":
                self._notify_file_processed(
                    file_path=ast_data.get("file_path", "unknown"),
                    file_id=result.get("file_id", "")
                )
                
            return result
        
        # Create appropriate batch processor based on config
        parallel_processing = self.config.get("parallel_processing", True)
        processor_type = "parallel" if parallel_processing else "sequential"
        batch_size = self.config.get("batch_size", 50)
        
        # Create the processor
        processor_config = {
            "batch_size": batch_size,
            "max_workers": self.config.get("max_workers", min(32, os.cpu_count() * 2))
        }
        
        processor = BatchProcessorFactory.create_processor(
            processor_type=processor_type,
            process_func=process_ast_func,
            config=processor_config
        )
        
        # Process the ASTs with progress tracking
        total_asts = len(asts)
        processed_count = 0
        start_time = time.time()
        
        # Define progress callback for batch processor
        def progress_callback(completed: int, total: int) -> None:
            nonlocal processed_count
            processed_count = completed
            if self.use_observer_pattern and total > 0:
                percentage = min(99.0, (completed / total) * 100)
                
                # Calculate metrics for progress message
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                
                self._notify_progress(
                    percentage=percentage,
                    message=f"Processed {completed}/{total} ASTs ({rate:.1f} ASTs/sec)"
                )
        
        # Set up callback if supported by the processor
        if hasattr(processor, "set_progress_callback"):
            processor.set_progress_callback(progress_callback)
        
        # Process the ASTs
        result = processor.process(asts)
        
        # Collect statistics
        success_count = 0
        error_count = 0
        file_ids = []
        
        for item in result.get("results", []):
            if item.get("status") == "success":
                success_count += 1
                file_ids.append(item.get("file_id"))
            else:
                error_count += 1
                # Notify observers of errors
                if self.use_observer_pattern:
                    self._notify_error(
                        error_message=f"Error processing AST: {item.get('error', 'Unknown error')}",
                        details={"file_path": item.get("file_path", "unknown")}
                    )
        
        # Notify observers of batch processing completion
        if self.use_observer_pattern:
            # Final progress update
            self._notify_progress(100.0, f"Completed processing {success_count}/{total_asts} ASTs")
            
            # Stage completion event
            stage_time = time.time() - start_time
            stage_event = self.observer_manager.create_stage_completed_event(
                source=self.__class__.__name__,
                stage_name="BatchProcessing",
                duration=stage_time
            )
            self.observer_manager.notify_observers(stage_event)
        
        return {
            "files_processed": success_count,
            "files_failed": error_count,
            "file_ids": file_ids,
            "errors": result.get("errors", [])
        }
    
    def _create_file_node(self, file_path: str, language: str, repository: str,
                      repository_url: str, commit: str, branch: str) -> str:
        """
        Create a File node in the graph.
        
        Args:
            file_path: Path to the file
            language: Programming language
            repository: Repository name
            repository_url: Repository URL
            commit: Commit hash
            branch: Branch name
            
        Returns:
            ID of the created File node
        """
        # Generate a unique ID for the file that includes repository information
        # This ensures uniqueness across repositories even if file paths are similar
        file_id = hashlib.md5(f"{repository}:{file_path}".encode()).hexdigest()
        
        # Create properties dictionary
        file_props = {
            "id": file_id,
            "path": file_path,
            "language": language,
            "repository": repository,
            "repository_url": repository_url,
            "commit": commit,
            "branch": branch,
            "last_updated": int(time.time())
        }
        
        if self.use_command_pattern:
            # Use Command pattern
            command = CreateNodesCommand(
                neo4j_tool=self.neo4j_tool,
                node_type="File",
                nodes=[file_props],
                config={"batch_size": 1}  # Single node operation
            )
            
            try:
                result = self.command_invoker.execute_command(command)
                self.graph_stats["commands_executed"] += 1
                
                # Extract file ID from result
                if result and "results" in result and len(result["results"]) > 0:
                    return file_id  # We know the ID since we specified it
                else:
                    self.logger.error(f"Failed to create file node: {result}")
                    return ""
            except Exception as e:
                self.logger.error(f"Error creating file node via command: {e}")
                # Fall back to direct query if command fails
                self.logger.info("Falling back to direct query for file node creation")
        
        # Direct query approach (fallback or if command pattern disabled)
        return super()._create_file_node(
            file_path=file_path,
            language=language,
            repository=repository,
            repository_url=repository_url,
            commit=commit,
            branch=branch
        )
        
    def _batch_create_nodes(self, node_type: str, nodes: List[Dict[str, Any]]) -> List[str]:
        """
        Create nodes in a batch for better performance.
        
        Args:
            node_type: Type of node to create
            nodes: List of node data dictionaries
            
        Returns:
            List of created node IDs
        """
        if not nodes:
            return []
            
        if self.use_command_pattern:
            # Use Command pattern
            command = CreateNodesCommand(
                neo4j_tool=self.neo4j_tool,
                node_type=node_type,
                nodes=nodes,
                config={"batch_size": self.config.get("db_batch_size", 500)}
            )
            
            try:
                result = self.command_invoker.execute_command(command)
                self.graph_stats["commands_executed"] += 1
                
                # Extract IDs from results
                return [item.get("id") for item in result.get("results", [])]
            except Exception as e:
                self.logger.error(f"Error creating nodes via command: {e}")
                # Fall back to batch creation utility
                self.logger.info("Falling back to batch creation utility")
        
        # Use the batch creation utility
        result = batch_create_nodes(
            neo4j_tool=self.neo4j_tool,
            node_type=node_type,
            nodes=nodes,
            batch_size=self.config.get("db_batch_size", 500)
        )
        
        # Extract IDs from results
        return [item.get("id") for item in result.get("results", [])]
    
    def _batch_create_relationships(self, relationships: List[Dict[str, Any]],
                                   source_type: str = "Node", target_type: str = "Node") -> List[Dict[str, Any]]:
        """
        Create relationships in a batch for better performance.
        
        Args:
            relationships: List of relationship data dictionaries
            source_type: Type of source node
            target_type: Type of target node
            
        Returns:
            List of created relationship details
        """
        if not relationships:
            return []
            
        if self.use_command_pattern:
            # Use Command pattern
            command = CreateRelationshipsCommand(
                neo4j_tool=self.neo4j_tool,
                relationships=relationships,
                source_type=source_type,
                target_type=target_type,
                config={"batch_size": self.config.get("db_batch_size", 500)}
            )
            
            try:
                result = self.command_invoker.execute_command(command)
                self.graph_stats["commands_executed"] += 1
                
                # Return results
                return result.get("results", [])
            except Exception as e:
                self.logger.error(f"Error creating relationships via command: {e}")
                # Fall back to batch creation utility
                self.logger.info("Falling back to batch creation utility")
        
        # Use the batch creation utility
        result = batch_create_relationships(
            neo4j_tool=self.neo4j_tool,
            relationships=relationships,
            source_type=source_type,
            target_type=target_type,
            batch_size=self.config.get("db_batch_size", 500)
        )
        
        # Return results
        return result.get("results", [])
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the knowledge graph from AST structures with placeholders.
        
        Args:
            input_data: Dictionary containing AST structures
            
        Returns:
            Dictionary with graph building results
        """
        # Notify observers of pipeline start
        repository = input_data.get("repository", "")
        if self.use_observer_pattern:
            start_event = self.observer_manager.create_pipeline_started_event(
                source=self.__class__.__name__,
                repository=repository
            )
            self.observer_manager.notify_observers(start_event)
        
        try:
            # For very large repositories, use batched processing instead of individual processing
            use_batched_processing = self.config.get("use_batched_processing", True)
            
            if use_batched_processing and len(input_data.get("asts", [])) > 100:
                result = self._run_batched(input_data)
            else:
                # For smaller repositories, use standard processing
                if self.use_observer_pattern:
                    # Notify of stage start
                    stage_event = self.observer_manager.create_stage_started_event(
                        source=self.__class__.__name__,
                        stage_name="StandardProcessing"
                    )
                    self.observer_manager.notify_observers(stage_event)
                    
                # Execute standard processing
                start_time = time.time()
                result = super().run(input_data)
                
                if self.use_observer_pattern:
                    # Notify of stage completion
                    stage_time = time.time() - start_time
                    stage_event = self.observer_manager.create_stage_completed_event(
                        source=self.__class__.__name__,
                        stage_name="StandardProcessing",
                        duration=stage_time
                    )
                    self.observer_manager.notify_observers(stage_event)
                
                # Perform a bulk resolution of all placeholders
                if self.create_placeholders and not self.immediate_resolution:
                    if self.use_observer_pattern:
                        # Notify of resolution stage start
                        stage_event = self.observer_manager.create_stage_started_event(
                            source=self.__class__.__name__,
                            stage_name="PlaceholderResolution"
                        )
                        self.observer_manager.notify_observers(stage_event)
                    
                    # Execute resolution
                    start_time = time.time()
                    resolution_stats = self._resolve_all_placeholders()
                    result["resolution_stats"] = resolution_stats
                    
                    if self.use_observer_pattern:
                        # Notify of resolution stage completion
                        stage_time = time.time() - start_time
                        stage_event = self.observer_manager.create_stage_completed_event(
                            source=self.__class__.__name__,
                            stage_name="PlaceholderResolution",
                            duration=stage_time
                        )
                        self.observer_manager.notify_observers(stage_event)
            
            # Notify observers of pipeline completion
            if self.use_observer_pattern:
                # Get statistics from stats observer if available
                stats = {}
                if hasattr(self, 'stats_observer'):
                    stats = self.stats_observer.get_statistics()
                
                # Add graph stats
                stats.update({
                    "graph_stats": self.graph_stats,
                    "files_processed": result.get("files_processed", 0),
                    "files_failed": result.get("files_failed", 0)
                })
                
                # Create and notify completion event
                completion_event = self.observer_manager.create_pipeline_completed_event(
                    source=self.__class__.__name__,
                    repository=repository,
                    stats=stats
                )
                self.observer_manager.notify_observers(completion_event)
            
            return result
            
        except Exception as e:
            # Log the error
            self.logger.exception(f"Error running graph builder: {str(e)}")
            
            # Notify observers of pipeline failure
            if self.use_observer_pattern:
                failure_event = self.observer_manager.create_pipeline_failed_event(
                    source=self.__class__.__name__,
                    repository=repository,
                    error=str(e)
                )
                self.observer_manager.notify_observers(failure_event)
            
            # Return error result
            return {
                "status": "error",
                "repository": repository,
                "error": str(e)
            }
            
    def _run_batched(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the graph builder with batched processing for large repositories.
        
        Args:
            input_data: Dictionary containing AST structures
            
        Returns:
            Dictionary with graph building results
        """
        start_time = time.time()
        
        # Extract input parameters
        repository = input_data.get("repository", "")
        repository_url = input_data.get("repository_url", "")
        commit = input_data.get("commit", "")
        branch = input_data.get("branch", "main")
        asts = input_data.get("asts", [])
        is_full_indexing = input_data.get("is_full_indexing", False)
        
        try:
            # Notify of repository data clearing if needed
            if is_full_indexing and repository:
                if self.use_observer_pattern:
                    self._notify_progress(
                        0.0, 
                        f"Clearing existing data for repository: {repository}"
                    )
                
                self.logger.info(f"Performing full indexing for repository: {repository}")
                self.neo4j_tool.clear_repository_data(repository)
            
            # Process ASTs in batches
            if self.use_observer_pattern:
                # Initial progress before batch processing
                self._notify_progress(5.0, f"Starting batch processing of {len(asts)} ASTs")
            
            batch_result = self._batch_process_asts(
                asts=asts,
                repository=repository,
                repository_url=repository_url,
                commit=commit,
                branch=branch
            )
            
            # Perform bulk resolution if needed
            if self.create_placeholders and not self.immediate_resolution:
                if self.use_observer_pattern:
                    # Notify of resolution stage start
                    stage_event = self.observer_manager.create_stage_started_event(
                        source=self.__class__.__name__,
                        stage_name="PlaceholderResolution"
                    )
                    self.observer_manager.notify_observers(stage_event)
                    
                    # Progress update
                    self._notify_progress(90.0, "Resolving placeholders")
                    
                # Execute resolution
                resolution_start = time.time()
                resolution_stats = self._resolve_all_placeholders()
                batch_result["resolution_stats"] = resolution_stats
                
                if self.use_observer_pattern:
                    # Notify of resolution stage completion
                    resolution_time = time.time() - resolution_start
                    stage_event = self.observer_manager.create_stage_completed_event(
                        source=self.__class__.__name__,
                        stage_name="PlaceholderResolution",
                        duration=resolution_time
                    )
                    self.observer_manager.notify_observers(stage_event)
            
            # Final progress update
            if self.use_observer_pattern:
                self._notify_progress(100.0, "Processing complete")
            
            # Add stats and timing
            end_time = time.time()
            processing_time = end_time - start_time
            
            return {
                "status": "success",
                "repository": repository,
                "commit": commit,
                "branch": branch,
                "files_processed": batch_result.get("files_processed", 0),
                "files_failed": batch_result.get("files_failed", 0),
                "graph_stats": self.graph_stats,
                "processing_time": processing_time,
                "errors": batch_result.get("errors", [])
            }
            
        except Exception as e:
            # Log the error
            self.logger.exception(f"Error in batched processing: {str(e)}")
            
            # Notify observers of error
            if self.use_observer_pattern:
                self._notify_error(
                    error_message=f"Batch processing failed: {str(e)}",
                    details={"repository": repository}
                )
            
            # Return error result
            return {
                "status": "error",
                "repository": repository,
                "error": str(e),
                "files_processed": 0,
                "files_failed": len(asts)
            }


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    config = {
        "neo4j_config": {
            "NEO4J_URI": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USER": os.environ.get("NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", "password")
        },
        "create_placeholders": True,
        "immediate_resolution": True,
        "resolution_strategy": "join",
        "use_iterator_pattern": True,
        "use_composite_pattern": True,
        "use_command_pattern": True,
        "use_strategy_pattern": True,
        "use_observer_pattern": True,
        
        # Default strategy (optional, otherwise auto-selected based on AST size)
        "default_processing_strategy": None,
        
        # Configuration for strategy implementations
        "strategy_config": {
            "batch_size": 100,
            "max_workers": min(8, os.cpu_count()),
            "streaming_chunk_size": 1000
        },
        
        # Configuration for indexing observers
        "observer_config": {
            # Enable console observer for terminal output
            "console_observer": True,
            "console_verbose": False,
            
            # Enable file observer for persistent logging
            "file_observer": True,
            "file_observer_path": "indexing_events.log",
            
            # Enable progress bar for interactive sessions
            "progress_bar": True
        }
    }
    
    runner = EnhancedGraphBuilderRunner(config)
    
    # Input would be provided by the orchestration layer
    print("Enhanced Graph Builder ready. Use the runner's run() method with AST input data.")