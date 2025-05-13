"""
Query Agent

Agent responsible for processing natural language queries about code.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple

from google.adk import Agent
from google.adk.tools.google_api_tool import AgentContext, HandlerResponse
from google.adk.tools.google_api_tool import ToolResponse

from code_indexer.tools.embedding_tool import EmbeddingTool


class QueryAgent(Agent):
    """
    Agent responsible for processing natural language queries about code.
    
    This agent takes natural language queries from users, analyzes them,
    and transforms them into structured queries that can be processed by
    specialized search agents (vector search, graph search, etc.).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the query agent.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self.logger = logging.getLogger("query_agent")
        
        # Configure defaults
        self.embedding_dimension = config.get("embedding_dimension", 1536)
        self.llm_model = config.get("llm_model", "gpt-4")
        self.multi_query_expansion = config.get("multi_query_expansion", True)
        self.expansion_count = config.get("expansion_count", 3)
        
        # Available tools
        self.embedding_tool = None
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        self.context = context
        
        # Get embedding tool
        tool_response = context.get_tool("embedding_tool")
        if tool_response.status.is_success():
            self.embedding_tool = tool_response.tool
            self.logger.info("Successfully acquired embedding tool")
        else:
            self.logger.error("Failed to acquire embedding tool: %s", 
                            tool_response.status.message)
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Process a query from the user.
        
        Args:
            input_data: Dictionary containing the query and other parameters
            
        Returns:
            HandlerResponse with processed query information
        """
        self.logger.info("Processing query")
        
        # Extract query from input
        query = input_data.get("query", "")
        if not query:
            return HandlerResponse.error("No query provided")
        
        # Extract optional parameters
        search_type = input_data.get("search_type", "hybrid")  # hybrid, vector, graph
        max_results = input_data.get("max_results", 10)
        filters = input_data.get("filters", {})
        
        # Process the query to extract intent and parameters
        query_analysis = self._analyze_query(query)
        
        # Generate vector embeddings for the query
        query_embeddings = self._generate_query_embeddings(
            query, 
            query_analysis.get("focus_phrases", [])
        )
        
        # Prepare the search specification
        search_spec = {
            "original_query": query,
            "analyzed_query": query_analysis,
            "search_type": search_type,
            "embeddings": query_embeddings,
            "max_results": max_results,
            "filters": self._enhance_filters(filters, query_analysis),
        }
        
        self.logger.info("Query processed successfully")
        return HandlerResponse.success({"search_spec": search_spec})
    
    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze the query to extract intent, focus, and parameters.
        
        Args:
            query: User's natural language query
            
        Returns:
            Dictionary with query analysis
        """
        # In a real implementation, this would use an LLM to analyze the query
        # For now, we'll use a simple approach to extract key information
        
        # Determine the primary intent of the query
        intents = self._detect_intent(query)
        
        # Extract code-related entities mentioned in the query
        entities = self._extract_entities(query)
        
        # Identify focus phrases that should be used for embeddings
        focus_phrases = self._extract_focus_phrases(query)
        
        # Rewrite the query for better search results
        rewritten_query = self._rewrite_query(query)
        
        analysis = {
            "intents": intents,
            "entities": entities,
            "focus_phrases": focus_phrases,
            "rewritten_query": rewritten_query,
            "requires_code_execution": "execution" in intents,
            "requires_structural_search": any(i in intents for i in ["definition", "usage", "inheritance"]),
        }
        
        return analysis
    
    def _detect_intent(self, query: str) -> List[str]:
        """
        Detect the intent of the query.
        
        Args:
            query: User's natural language query
            
        Returns:
            List of intents detected in the query
        """
        # This is a placeholder implementation
        # In production, this would use an LLM to analyze intent
        
        intents = []
        
        # Check for definition-finding intent
        if any(phrase in query.lower() for phrase in ["find definition", "where is defined", "definition of", "how is implemented"]):
            intents.append("definition")
        
        # Check for usage-finding intent
        if any(phrase in query.lower() for phrase in ["how is used", "where is used", "usage of", "references to"]):
            intents.append("usage")
        
        # Check for explanation intent
        if any(phrase in query.lower() for phrase in ["explain", "how does", "what does", "why does"]):
            intents.append("explanation")
        
        # Check for code generation intent
        if any(phrase in query.lower() for phrase in ["implement", "create", "write code", "generate"]):
            intents.append("generation")
        
        # Check for code execution intent
        if any(phrase in query.lower() for phrase in ["run", "execute", "performance", "time complexity"]):
            intents.append("execution")
        
        # Check for inheritance/class relationship intent
        if any(phrase in query.lower() for phrase in ["inherits", "extends", "parent class", "child class", "subclass"]):
            intents.append("inheritance")
        
        # Default intent if none detected
        if not intents:
            intents.append("information")
        
        return intents
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract code-related entities from the query.
        
        Args:
            query: User's natural language query
            
        Returns:
            Dictionary mapping entity types to lists of entity names
        """
        # This is a placeholder implementation
        # In production, this would use an LLM or specialized models
        
        entities = {
            "functions": [],
            "classes": [],
            "methods": [],
            "files": [],
            "variables": [],
            "packages": [],
        }
        
        # Simple pattern-based extraction (not robust)
        words = query.replace("(", " ").replace(")", " ").replace(".", " ").split()
        
        for word in words:
            # Check if word might be a function (CamelCase or snake_case with "function", "method" nearby)
            if (any(char.isupper() for char in word) and any(char.islower() for char in word)) or "_" in word:
                context_words = query.lower().split()
                if "function" in context_words or "method" in context_words:
                    if "(" in query or ")" in query or word.endswith("()"):
                        if word not in entities["functions"]:
                            entities["functions"].append(word.strip("()"))
                elif "class" in context_words:
                    if word not in entities["classes"]:
                        entities["classes"].append(word)
                elif "file" in context_words or ".py" in query or ".js" in query:
                    if word not in entities["files"] and "." in word:
                        entities["files"].append(word)
        
        return entities
    
    def _extract_focus_phrases(self, query: str) -> List[str]:
        """
        Extract key phrases from the query to focus embeddings.
        
        Args:
            query: User's natural language query
            
        Returns:
            List of focus phrases
        """
        # In production, this would use an LLM to extract key phrases
        # For now, just use the whole query
        return [query]
    
    def _rewrite_query(self, query: str) -> str:
        """
        Rewrite the query for better search results.
        
        Args:
            query: User's natural language query
            
        Returns:
            Rewritten query
        """
        # In production, this would use an LLM to rewrite the query
        # For now, just return the original query
        return query
    
    def _generate_query_embeddings(self, query: str, focus_phrases: List[str]) -> Dict[str, Any]:
        """
        Generate vector embeddings for the query.
        
        Args:
            query: User's natural language query
            focus_phrases: Key phrases extracted from the query
            
        Returns:
            Dictionary with the generated embeddings
        """
        if not self.embedding_tool:
            self.logger.error("Embedding tool not available")
            return {"primary": [], "expanded": []}
        
        embeddings_result = {
            "primary": [],
            "expanded": []
        }
        
        # Generate primary embedding for the original query
        try:
            tool_response = self.embedding_tool.generate_embedding({
                "text": query,
                "model": self.config.get("embedding_model", "default")
            })
            
            if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                embeddings_result["primary"] = tool_response.data.get("embedding", [])
            else:
                self.logger.error("Failed to generate primary embedding")
        except Exception as e:
            self.logger.error(f"Error generating primary embedding: {e}")
        
        # Generate embeddings for focus phrases if multi-query expansion is enabled
        if self.multi_query_expansion and focus_phrases:
            expanded_queries = self._expand_query(query, focus_phrases)
            expanded_embeddings = []
            
            for expanded_query in expanded_queries:
                try:
                    tool_response = self.embedding_tool.generate_embedding({
                        "text": expanded_query,
                        "model": self.config.get("embedding_model", "default")
                    })
                    
                    if isinstance(tool_response, ToolResponse) and tool_response.status.is_success():
                        expanded_embeddings.append({
                            "query": expanded_query,
                            "embedding": tool_response.data.get("embedding", [])
                        })
                except Exception as e:
                    self.logger.error(f"Error generating expanded embedding: {e}")
            
            embeddings_result["expanded"] = expanded_embeddings
        
        return embeddings_result
    
    def _expand_query(self, query: str, focus_phrases: List[str]) -> List[str]:
        """
        Expand the query into multiple alternative queries.
        
        Args:
            query: Original query
            focus_phrases: Key phrases extracted from the query
            
        Returns:
            List of expanded queries
        """
        # In a real implementation, this would use an LLM to generate variations
        # For now, just create simple variations
        
        expanded = []
        
        # Create basic variations
        if "how" in query.lower():
            expanded.append(query.lower().replace("how", "what is the way"))
        
        if "where" in query.lower():
            expanded.append(query.lower().replace("where", "in which location"))
        
        if "find" in query.lower():
            expanded.append(query.lower().replace("find", "locate"))
        
        # If we don't have enough variations, add some generic ones
        if len(expanded) < self.expansion_count:
            expanded.append(f"code that {query}")
            expanded.append(f"implementation of {query}")
            expanded.append(f"function for {query}")
        
        # Limit to the configured count
        return expanded[:self.expansion_count]
    
    def _enhance_filters(self, user_filters: Dict[str, Any], 
                       query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance filters based on query analysis.
        
        Args:
            user_filters: User-provided filters
            query_analysis: Analysis of the query
            
        Returns:
            Enhanced filters
        """
        # Start with user-provided filters
        enhanced_filters = user_filters.copy()
        
        # Add language filters if detected in the query
        languages = self._detect_languages(query_analysis)
        if languages and "language" not in enhanced_filters:
            enhanced_filters["language"] = languages
        
        # Add entity type filters based on intent
        intents = query_analysis.get("intents", [])
        if "definition" in intents and "entity_type" not in enhanced_filters:
            enhanced_filters["entity_type"] = ["function", "class", "method", "module"]
        
        return enhanced_filters
    
    def _detect_languages(self, query_analysis: Dict[str, Any]) -> List[str]:
        """
        Detect programming languages mentioned in the query.
        
        Args:
            query_analysis: Analysis of the query
            
        Returns:
            List of detected languages
        """
        # This would be more sophisticated in a real implementation
        languages = []
        
        # Check the original query for language mentions
        query = query_analysis.get("original_query", "").lower()
        
        common_languages = {
            "python": ["python", "py", ".py"],
            "javascript": ["javascript", "js", ".js", "node"],
            "typescript": ["typescript", "ts", ".ts"],
            "java": ["java", ".java"],
            "go": ["golang", "go", ".go"],
            "ruby": ["ruby", "rb", ".rb"],
            "rust": ["rust", "rs", ".rs"],
            "c++": ["c++", "cpp", ".cpp"],
            "c#": ["c#", "csharp", ".cs"],
        }
        
        for lang, keywords in common_languages.items():
            if any(keyword in query for keyword in keywords):
                languages.append(lang)
        
        return languages