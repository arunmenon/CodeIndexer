"""
Enhanced Graph Builder with Call and Import Sites

An enhanced implementation of the graph builder that includes support for
placeholders for call sites and import sites, enabling accurate cross-file
relationship resolution.
"""

import os
import logging
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union

# Import direct implementation modules
from code_indexer.ingestion.direct.graph_builder import DirectGraphBuilderRunner, Neo4jToolWrapper
from code_indexer.ingestion.direct.neo4j_tool import DirectNeo4jTool
from code_indexer.utils.ast_utils import find_entity_in_ast, get_function_info, get_class_info


class EnhancedNeo4jTool(Neo4jToolWrapper):
    """
    Enhanced Neo4j Tool with support for call sites and cross-file relationship resolution.
    """
    
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
        
        # Additional configuration
        self.create_placeholders = self.config.get("create_placeholders", True)
        self.resolution_strategy = self.config.get("resolution_strategy", "join")
        self.immediate_resolution = self.config.get("immediate_resolution", True)
        
        # Set up optimized schema
        if self.neo4j_tool.connect():
            self.neo4j_tool.setup_optimized_schema()
            self.logger.info("Enhanced Neo4j schema setup complete")
        
        # Additional graph statistics
        self.graph_stats.update({
            "call_sites": 0,
            "import_sites": 0,
            "resolved_calls": 0,
            "resolved_imports": 0
        })
    
    def _extract_call_sites(self, ast_root: Dict[str, Any], file_id: str, 
                          current_function: Optional[Dict[str, Any]] = None, 
                          current_class: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract call sites from the AST and create placeholder nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file
            current_function: Current function context if inside a function
            current_class: Current class context if inside a class
            
        Returns:
            List of created call site nodes
        """
        call_sites = []
        
        # Find Call nodes in the AST
        call_nodes = find_entity_in_ast(ast_root, "Call")
        
        for call_node in call_nodes:
            # Ensure we have function information
            if "func" not in call_node.get("attributes", {}):
                continue
            
            func = call_node["attributes"]["func"]
            start_pos = call_node.get("start_position", {})
            end_pos = call_node.get("end_position", {})
            
            start_line = start_pos.get("row", 0)
            start_col = start_pos.get("column", 0)
            end_line = end_pos.get("row", 0)
            end_col = end_pos.get("column", 0)
            
            # Get current context
            caller_function_id = current_function.get("id") if current_function else None
            caller_class_id = current_class.get("id") if current_class else None
            
            # Extract call details
            call_info = self._extract_call_info(func)
            
            if call_info:
                # Generate a unique ID for the call site that includes repository information
                # This ensures uniqueness across repositories even if file paths are similar
                repo_identifier = ast_data.get("repository", "") or repository or ""
                call_id = hashlib.md5(
                    f"{repo_identifier}:{file_id}:{start_line}:{start_col}:{call_info['name']}".encode()
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
    
    def _extract_call_info(self, func_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract call information from a function node.
        
        Args:
            func_node: The function node from a Call AST
            
        Returns:
            Dictionary with call information or None
        """
        if not func_node:
            return None
            
        node_type = func_node.get("type")
        
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
                
        return None
    
    def _extract_import_sites(self, ast_root: Dict[str, Any], file_id: str) -> List[Dict[str, Any]]:
        """
        Extract import sites from the AST and create placeholder nodes.
        
        Args:
            ast_root: Root of the AST
            file_id: ID of the file
            
        Returns:
            List of created import site nodes
        """
        import_sites = []
        
        # Find Import and ImportFrom nodes
        import_nodes = find_entity_in_ast(ast_root, "Import")
        import_from_nodes = find_entity_in_ast(ast_root, "ImportFrom")
        
        # Process Import statements
        for import_node in import_nodes:
            if "names" not in import_node.get("attributes", {}):
                continue
                
            start_pos = import_node.get("start_position", {})
            end_pos = import_node.get("end_position", {})
            
            start_line = start_pos.get("row", 0)
            end_line = end_pos.get("row", 0)
            
            for alias in import_node["attributes"]["names"]:
                name = alias.get("name", "")
                asname = alias.get("asname", "")
                
                if name:
                    # Generate a unique ID for the import site that includes repository information
                    # This ensures uniqueness across repositories even if file paths are similar
                    repo_identifier = ast_data.get("repository", "") or repository or ""
                    import_id = hashlib.md5(
                        f"{repo_identifier}:{file_id}:import:{start_line}:{name}".encode()
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
            if "names" not in import_from_node.get("attributes", {}):
                continue
                
            module = import_from_node["attributes"].get("module", "")
            start_pos = import_from_node.get("start_position", {})
            end_pos = import_from_node.get("end_position", {})
            
            start_line = start_pos.get("row", 0)
            end_line = end_pos.get("row", 0)
            
            for alias in import_from_node["attributes"]["names"]:
                name = alias.get("name", "")
                asname = alias.get("asname", "")
                
                if name and module:
                    # Generate a unique ID for the import site that includes repository information
                    # This ensures uniqueness across repositories even if file paths are similar
                    repo_identifier = ast_data.get("repository", "") or repository or ""
                    import_id = hashlib.md5(
                        f"{repo_identifier}:{file_id}:import_from:{start_line}:{module}.{name}".encode()
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
            WITH cs, collect(f)[0] as best_function, collect(score)[0] as best_score
            MERGE (cs)-[r:RESOLVES_TO]->(best_function)
            SET r.score = best_score, r.timestamp = timestamp()
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
    
    def _process_ast(self, ast_data: Dict[str, Any], repository: str,
                   repository_url: str, commit: str, branch: str) -> Dict[str, Any]:
        """
        Process a single AST and build corresponding graph with placeholders.
        
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
            # Extract AST data
            file_path = ast_data.get("file_path", "")
            language = ast_data.get("language", "unknown")
            ast_root = ast_data.get("root", {})
            
            if not file_path or not ast_root:
                return {
                    "status": "error",
                    "error": "Missing file path or AST root"
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
                    "error": "Failed to create file node"
                }
            
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
                "import_sites": len(import_sites)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the knowledge graph from AST structures with placeholders.
        
        Args:
            input_data: Dictionary containing AST structures
            
        Returns:
            Dictionary with graph building results
        """
        result = super().run(input_data)
        
        # Perform a bulk resolution of all placeholders
        if self.create_placeholders and not self.immediate_resolution:
            resolution_stats = self._resolve_all_placeholders()
            result["resolution_stats"] = resolution_stats
        
        return result


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
        "resolution_strategy": "join" 
    }
    
    runner = EnhancedGraphBuilderRunner(config)
    
    # Input would be provided by the orchestration layer
    print("Enhanced Graph Builder ready. Use the runner's run() method with AST input data.")