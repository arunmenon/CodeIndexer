"""
Graph Search Agent

Agent responsible for performing structural code queries using the code knowledge graph.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Union

from google.adk.api.agent import Agent, AgentContext, HandlerResponse
from google.adk.api.tool import ToolResponse

class GraphSearchAgent(Agent):
    """
    Agent responsible for performing structural code queries.
    
    This agent translates query intents into graph database queries and
    retrieves code information based on structural relationships like
    inheritance, function calls, imports, etc.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the graph search agent.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self.logger = logging.getLogger("graph_search_agent")
        
        # Configure defaults
        self.default_limit = config.get("default_limit", 10)
        self.neo4j_db = config.get("neo4j_db", "neo4j")
        
        # Available tools
        self.neo4j_tool = None
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        self.context = context
        
        # Get Neo4j tool
        tool_response = context.get_tool("neo4j_tool")
        if tool_response.status.is_success():
            self.neo4j_tool = tool_response.tool
            self.logger.info("Successfully acquired Neo4j tool")
        else:
            self.logger.error("Failed to acquire Neo4j tool: %s", 
                              tool_response.status.message)
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Perform graph search for a query.
        
        Args:
            input_data: Dictionary containing search parameters
            
        Returns:
            HandlerResponse with search results
        """
        self.logger.info("Performing graph search")
        
        # Extract search specification
        search_spec = input_data.get("search_spec", {})
        if not search_spec:
            return HandlerResponse.error("No search specification provided")
        
        # Extract query analysis
        query_analysis = search_spec.get("analyzed_query", {})
        intents = query_analysis.get("intents", [])
        entities = query_analysis.get("entities", {})
        
        # Extract search parameters
        max_results = input_data.get("max_results", self.default_limit)
        
        # Determine which type of graph search to perform based on intent
        if "definition" in intents:
            results = self._find_definitions(entities, max_results)
        elif "usage" in intents:
            results = self._find_usages(entities, max_results)
        elif "inheritance" in intents:
            results = self._find_inheritance_relationships(entities, max_results)
        elif "imports" in intents:
            results = self._find_imports(entities, max_results)
        else:
            # Default to a general search
            results = self._general_search(query_analysis, max_results)
        
        self.logger.info(f"Graph search completed: {len(results)} results found")
        return HandlerResponse.success({
            "results": results,
            "total_count": len(results),
            "query_type": self._determine_query_type(intents)
        })
    
    def _find_definitions(self, entities: Dict[str, List[str]], 
                         limit: int) -> List[Dict[str, Any]]:
        """
        Find definitions of entities in the code.
        
        Args:
            entities: Dictionary of entity types and names
            limit: Maximum number of results to return
            
        Returns:
            List of entity definitions
        """
        if not self.neo4j_tool:
            self.logger.error("Neo4j tool not available")
            return []
        
        results = []
        
        # Look for function definitions
        functions = entities.get("functions", [])
        if functions:
            for function_name in functions:
                # Construct Cypher query to find function definitions
                cypher_query = f"""
                MATCH (func:Function {{name: '{function_name}'}})
                RETURN func, func.filePath as filePath, func.startLine as startLine, 
                       func.endLine as endLine, func.language as language
                LIMIT {limit}
                """
                
                try:
                    # Execute the query
                    tool_response = self.neo4j_tool.execute_query({
                        "query": cypher_query,
                        "database": self.neo4j_db
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        query_results = tool_response.data.get("results", [])
                        
                        for result in query_results:
                            func_data = result.get("func", {})
                            
                            results.append({
                                "entity_type": "function",
                                "entity_id": function_name,
                                "file_path": result.get("filePath", ""),
                                "start_line": result.get("startLine", 0),
                                "end_line": result.get("endLine", 0),
                                "language": result.get("language", ""),
                                "definition_type": "function",
                                "parameters": func_data.get("parameters", []),
                                "return_type": func_data.get("returnType", ""),
                                "code_content": None,  # Would be populated in real implementation
                                "search_type": "definition"
                            })
                    
                except Exception as e:
                    self.logger.error(f"Error finding function definitions: {e}")
        
        # Look for class definitions
        classes = entities.get("classes", [])
        if classes:
            for class_name in classes:
                # Construct Cypher query to find class definitions
                cypher_query = f"""
                MATCH (cls:Class {{name: '{class_name}'}})
                OPTIONAL MATCH (cls)-[:EXTENDS]->(parent:Class)
                RETURN cls, cls.filePath as filePath, cls.startLine as startLine, 
                       cls.endLine as endLine, cls.language as language,
                       parent.name as parentClass
                LIMIT {limit}
                """
                
                try:
                    # Execute the query
                    tool_response = self.neo4j_tool.execute_query({
                        "query": cypher_query,
                        "database": self.neo4j_db
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        query_results = tool_response.data.get("results", [])
                        
                        for result in query_results:
                            cls_data = result.get("cls", {})
                            
                            results.append({
                                "entity_type": "class",
                                "entity_id": class_name,
                                "file_path": result.get("filePath", ""),
                                "start_line": result.get("startLine", 0),
                                "end_line": result.get("endLine", 0),
                                "language": result.get("language", ""),
                                "definition_type": "class",
                                "parent_class": result.get("parentClass", ""),
                                "code_content": None,  # Would be populated in real implementation
                                "search_type": "definition"
                            })
                
                except Exception as e:
                    self.logger.error(f"Error finding class definitions: {e}")
        
        return results
    
    def _find_usages(self, entities: Dict[str, List[str]], 
                   limit: int) -> List[Dict[str, Any]]:
        """
        Find usages of entities in the code.
        
        Args:
            entities: Dictionary of entity types and names
            limit: Maximum number of results to return
            
        Returns:
            List of entity usages
        """
        if not self.neo4j_tool:
            self.logger.error("Neo4j tool not available")
            return []
        
        results = []
        
        # Look for function usages
        functions = entities.get("functions", [])
        if functions:
            for function_name in functions:
                # Construct Cypher query to find function usages
                cypher_query = f"""
                MATCH (func:Function {{name: '{function_name}'}})<-[:CALLS]-(caller)
                RETURN caller, caller.name as callerName, caller.filePath as filePath, 
                       caller.startLine as startLine, caller.endLine as endLine,
                       caller.language as language, labels(caller) as callerType
                LIMIT {limit}
                """
                
                try:
                    # Execute the query
                    tool_response = self.neo4j_tool.execute_query({
                        "query": cypher_query,
                        "database": self.neo4j_db
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        query_results = tool_response.data.get("results", [])
                        
                        for result in query_results:
                            caller_type = result.get("callerType", [""])[0]
                            
                            results.append({
                                "entity_type": "function",
                                "entity_id": function_name,
                                "file_path": result.get("filePath", ""),
                                "start_line": result.get("startLine", 0),
                                "end_line": result.get("endLine", 0),
                                "language": result.get("language", ""),
                                "caller_type": caller_type.lower(),
                                "caller_name": result.get("callerName", ""),
                                "code_content": None,  # Would be populated in real implementation
                                "search_type": "usage"
                            })
                
                except Exception as e:
                    self.logger.error(f"Error finding function usages: {e}")
        
        # Look for class usages (instantiations)
        classes = entities.get("classes", [])
        if classes:
            for class_name in classes:
                # Construct Cypher query to find class instantiations
                cypher_query = f"""
                MATCH (cls:Class {{name: '{class_name}'}})<-[:INSTANTIATES]-(caller)
                RETURN caller, caller.name as callerName, caller.filePath as filePath, 
                       caller.startLine as startLine, caller.endLine as endLine,
                       caller.language as language, labels(caller) as callerType
                LIMIT {limit}
                """
                
                try:
                    # Execute the query
                    tool_response = self.neo4j_tool.execute_query({
                        "query": cypher_query,
                        "database": self.neo4j_db
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        query_results = tool_response.data.get("results", [])
                        
                        for result in query_results:
                            caller_type = result.get("callerType", [""])[0]
                            
                            results.append({
                                "entity_type": "class",
                                "entity_id": class_name,
                                "file_path": result.get("filePath", ""),
                                "start_line": result.get("startLine", 0),
                                "end_line": result.get("endLine", 0),
                                "language": result.get("language", ""),
                                "usage_type": "instantiation",
                                "caller_type": caller_type.lower(),
                                "caller_name": result.get("callerName", ""),
                                "code_content": None,  # Would be populated in real implementation
                                "search_type": "usage"
                            })
                
                except Exception as e:
                    self.logger.error(f"Error finding class instantiations: {e}")
        
        return results
    
    def _find_inheritance_relationships(self, entities: Dict[str, List[str]], 
                                      limit: int) -> List[Dict[str, Any]]:
        """
        Find inheritance relationships between classes.
        
        Args:
            entities: Dictionary of entity types and names
            limit: Maximum number of results to return
            
        Returns:
            List of inheritance relationships
        """
        if not self.neo4j_tool:
            self.logger.error("Neo4j tool not available")
            return []
        
        results = []
        
        # Look for inheritance relationships for classes
        classes = entities.get("classes", [])
        if classes:
            for class_name in classes:
                # Find subclasses (classes that inherit from the target class)
                cypher_query = f"""
                MATCH (cls:Class {{name: '{class_name}'}})<-[:EXTENDS]-(subclass:Class)
                RETURN subclass.name as subclassName, subclass.filePath as filePath, 
                       subclass.startLine as startLine, subclass.endLine as endLine,
                       subclass.language as language
                LIMIT {limit}
                """
                
                try:
                    # Execute the query
                    tool_response = self.neo4j_tool.execute_query({
                        "query": cypher_query,
                        "database": self.neo4j_db
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        query_results = tool_response.data.get("results", [])
                        
                        for result in query_results:
                            results.append({
                                "entity_type": "class",
                                "entity_id": class_name,
                                "relationship_type": "parent",
                                "related_entity": result.get("subclassName", ""),
                                "related_type": "class",
                                "file_path": result.get("filePath", ""),
                                "start_line": result.get("startLine", 0),
                                "end_line": result.get("endLine", 0),
                                "language": result.get("language", ""),
                                "code_content": None,  # Would be populated in real implementation
                                "search_type": "inheritance"
                            })
                
                except Exception as e:
                    self.logger.error(f"Error finding inheritance relationships: {e}")
                
                # Find parent classes (classes that the target class inherits from)
                cypher_query = f"""
                MATCH (cls:Class {{name: '{class_name}'}})-[:EXTENDS]->(parent:Class)
                RETURN parent.name as parentName, parent.filePath as filePath, 
                       parent.startLine as startLine, parent.endLine as endLine,
                       parent.language as language
                LIMIT {limit}
                """
                
                try:
                    # Execute the query
                    tool_response = self.neo4j_tool.execute_query({
                        "query": cypher_query,
                        "database": self.neo4j_db
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        query_results = tool_response.data.get("results", [])
                        
                        for result in query_results:
                            results.append({
                                "entity_type": "class",
                                "entity_id": class_name,
                                "relationship_type": "child",
                                "related_entity": result.get("parentName", ""),
                                "related_type": "class",
                                "file_path": result.get("filePath", ""),
                                "start_line": result.get("startLine", 0),
                                "end_line": result.get("endLine", 0),
                                "language": result.get("language", ""),
                                "code_content": None,  # Would be populated in real implementation
                                "search_type": "inheritance"
                            })
                
                except Exception as e:
                    self.logger.error(f"Error finding inheritance relationships: {e}")
        
        return results
    
    def _find_imports(self, entities: Dict[str, List[str]], 
                    limit: int) -> List[Dict[str, Any]]:
        """
        Find import relationships for modules and packages.
        
        Args:
            entities: Dictionary of entity types and names
            limit: Maximum number of results to return
            
        Returns:
            List of import relationships
        """
        if not self.neo4j_tool:
            self.logger.error("Neo4j tool not available")
            return []
        
        results = []
        
        # Look for imports of packages and modules
        packages = entities.get("packages", [])
        if packages:
            for package_name in packages:
                # Find files that import this package
                cypher_query = f"""
                MATCH (file:File)-[:IMPORTS]->(:Module {{name: '{package_name}'}})
                RETURN file.path as filePath, file.language as language
                LIMIT {limit}
                """
                
                try:
                    # Execute the query
                    tool_response = self.neo4j_tool.execute_query({
                        "query": cypher_query,
                        "database": self.neo4j_db
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        query_results = tool_response.data.get("results", [])
                        
                        for result in query_results:
                            results.append({
                                "entity_type": "package",
                                "entity_id": package_name,
                                "relationship_type": "imported_by",
                                "file_path": result.get("filePath", ""),
                                "language": result.get("language", ""),
                                "code_content": None,  # Would be populated in real implementation
                                "search_type": "import"
                            })
                
                except Exception as e:
                    self.logger.error(f"Error finding import relationships: {e}")
        
        return results
    
    def _general_search(self, query_analysis: Dict[str, Any], 
                      limit: int) -> List[Dict[str, Any]]:
        """
        Perform a general search based on query analysis.
        
        Args:
            query_analysis: Dictionary with query analysis
            limit: Maximum number of results to return
            
        Returns:
            List of search results
        """
        if not self.neo4j_tool:
            self.logger.error("Neo4j tool not available")
            return []
        
        results = []
        
        # Get the original query
        original_query = query_analysis.get("original_query", "")
        if not original_query:
            return []
        
        # Extract names that might be code identifiers
        # This is a simple approach - a real implementation would use NLP or LLMs
        words = original_query.replace(".", " ").replace("(", " ").replace(")", " ").split()
        potential_identifiers = [word for word in words 
                                if word[0].isalpha() and len(word) > 2 
                                and (word[0].islower() or word[0].isupper())]
        
        if potential_identifiers:
            # Construct a Cypher query that searches for potential identifiers
            identifier_list = ", ".join([f"'{ident}'" for ident in potential_identifiers])
            cypher_query = f"""
            MATCH (n) 
            WHERE (n:Function OR n:Class OR n:Method OR n:Variable) AND n.name IN [{identifier_list}]
            RETURN n, n.name as name, n.filePath as filePath, n.startLine as startLine, 
                   n.endLine as endLine, n.language as language, labels(n) as nodeType
            LIMIT {limit}
            """
            
            try:
                # Execute the query
                tool_response = self.neo4j_tool.execute_query({
                    "query": cypher_query,
                    "database": self.neo4j_db
                })
                
                if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                    query_results = tool_response.data.get("results", [])
                    
                    for result in query_results:
                        node_type = result.get("nodeType", [""])[0]
                        
                        results.append({
                            "entity_type": node_type.lower(),
                            "entity_id": result.get("name", ""),
                            "file_path": result.get("filePath", ""),
                            "start_line": result.get("startLine", 0),
                            "end_line": result.get("endLine", 0),
                            "language": result.get("language", ""),
                            "code_content": None,  # Would be populated in real implementation
                            "search_type": "general"
                        })
            
            except Exception as e:
                self.logger.error(f"Error performing general search: {e}")
        
        return results
    
    def _determine_query_type(self, intents: List[str]) -> str:
        """
        Determine the query type based on intents.
        
        Args:
            intents: List of query intents
            
        Returns:
            Query type string
        """
        if "definition" in intents:
            return "definition"
        elif "usage" in intents:
            return "usage"
        elif "inheritance" in intents:
            return "inheritance"
        elif "imports" in intents:
            return "import"
        else:
            return "general"