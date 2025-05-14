"""
Answer Composer Agent

Agent responsible for synthesizing search results into coherent answers.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Union

from google.adk import Agent, AgentSpec
from google.adk.runtime.context import AgentContext
from google.adk.runtime.responses import HandlerResponse, ToolResponse, ToolStatus


class AnswerComposerAgent(Agent):
    """
    Agent responsible for synthesizing search results into coherent answers.
    
    This agent takes results from both vector search and graph search,
    combines them, and generates natural language answers that respond
    to the user's original query.
    """
    
    def __init__(self, name: str = "answer_composer_agent", **kwargs):
        """
        Initialize the answer composer agent.
        
        Args:
            name: Agent name
            **kwargs: Additional parameters including config
        """
        super().__init__(name=name)
        self.config = kwargs.get("config", {})
        self.logger = logging.getLogger(name)
        
        # Configure defaults
        self.max_code_snippets = self.config.get("max_code_snippets", 3)
        self.include_explanations = self.config.get("include_explanations", True)
        self.llm_model = self.config.get("llm_model", "gpt-4")
        self.answer_style = self.config.get("answer_style", "concise")  # concise, detailed
        
        # Available tools
        self.embedding_tool = None
    
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools and environment
        """
        self.context = context
        
        # Get embedding tool for potential follow-up queries
        tool_response = context.get_tool("embedding_tool")
        if tool_response.status.is_success():
            self.embedding_tool = tool_response.tool
            self.logger.info("Successfully acquired embedding tool")
        else:
            self.logger.error("Failed to acquire embedding tool: %s", 
                             tool_response.status.message)
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Generate an answer based on search results.
        
        Args:
            input_data: Dictionary containing search results and query information
            
        Returns:
            HandlerResponse with the generated answer
        """
        self.logger.info("Composing answer from search results")
        
        # Extract data from input
        original_query = input_data.get("original_query", "")
        search_spec = input_data.get("search_spec", {})
        query_analysis = search_spec.get("analyzed_query", {})
        vector_results = input_data.get("vector_results", [])
        graph_results = input_data.get("graph_results", [])
        
        if not original_query:
            return HandlerResponse.error("No query provided")
        
        if not vector_results and not graph_results:
            return HandlerResponse.success({
                "answer": "I couldn't find any relevant information about your query in the codebase.",
                "results": [],
                "query": original_query
            })
        
        # Combine and rank results
        combined_results = self._combine_results(vector_results, graph_results)
        
        # Generate the answer
        answer = self._generate_answer(original_query, query_analysis, combined_results)
        
        # Select the best code snippets to include
        selected_snippets = self._select_code_snippets(combined_results)
        
        # Format the answer for display
        formatted_answer = {
            "answer": answer,
            "code_snippets": selected_snippets,
            "query": original_query,
            "total_results": len(combined_results),
            "result_types": self._count_result_types(combined_results)
        }
        
        self.logger.info("Answer composed successfully")
        return HandlerResponse.success(formatted_answer)
    
    def _combine_results(self, vector_results: List[Dict[str, Any]], 
                       graph_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Combine and rank results from different search agents.
        
        Args:
            vector_results: Results from vector search
            graph_results: Results from graph search
            
        Returns:
            Combined and ranked results
        """
        # Track seen file paths and lines to avoid duplicates
        seen_locations = set()
        
        # Combine results and mark their source
        combined = []
        
        # Add vector results
        for result in vector_results:
            file_path = result.get("file_path", "")
            start_line = result.get("start_line", 0)
            end_line = result.get("end_line", 0)
            
            location_key = f"{file_path}:{start_line}-{end_line}"
            if location_key in seen_locations:
                continue
                
            seen_locations.add(location_key)
            result["source"] = "vector"
            combined.append(result)
        
        # Add graph results
        for result in graph_results:
            file_path = result.get("file_path", "")
            start_line = result.get("start_line", 0)
            end_line = result.get("end_line", 0)
            
            location_key = f"{file_path}:{start_line}-{end_line}"
            if location_key in seen_locations:
                # Update existing result with graph information
                for existing in combined:
                    existing_path = existing.get("file_path", "")
                    existing_start = existing.get("start_line", 0)
                    existing_end = existing.get("end_line", 0)
                    
                    if file_path == existing_path and start_line == existing_start and end_line == existing_end:
                        existing["source"] = "both"
                        
                        # Merge additional information
                        for key, value in result.items():
                            if key not in existing or not existing[key]:
                                existing[key] = value
                                
                        break
            else:
                seen_locations.add(location_key)
                result["source"] = "graph"
                combined.append(result)
        
        # Rank the combined results
        ranked_results = self._rank_results(combined)
        
        return ranked_results
    
    def _rank_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank results based on relevance and source.
        
        Args:
            results: Combined search results
            
        Returns:
            Ranked results
        """
        # Assign a score to each result
        for result in results:
            score = 0.0
            
            # Base score from vector search (if available)
            if "score" in result:
                score = result["score"]
            elif result.get("source") == "graph":
                score = 0.7  # Default score for graph results
            
            # Boost score based on source
            if result.get("source") == "both":
                score *= 1.2  # Boost for results found by both methods
            
            # Boost based on entity type
            entity_type = result.get("entity_type", "").lower()
            if entity_type in ["function", "class", "method"]:
                score *= 1.1  # Boost for important entity types
            
            # Boost for definition search type
            search_type = result.get("search_type", "").lower()
            if search_type == "definition":
                score *= 1.1  # Boost for definitions
            
            # Ensure score is within range
            result["rank_score"] = min(score, 1.0)
        
        # Sort by rank score
        ranked = sorted(results, key=lambda x: x.get("rank_score", 0.0), reverse=True)
        
        return ranked
    
    def _generate_answer(self, query: str, query_analysis: Dict[str, Any], 
                       results: List[Dict[str, Any]]) -> str:
        """
        Generate a natural language answer based on the query and results.
        
        Args:
            query: Original user query
            query_analysis: Analysis of the query
            results: Ranked search results
            
        Returns:
            Generated answer text
        """
        # In a real implementation, this would use an LLM to generate the answer
        # For now, we'll generate a template-based answer
        
        if not results:
            return "I couldn't find any relevant information about your query in the codebase."
        
        # Extract key information from results
        entity_counts = {}
        entity_names = set()
        file_paths = set()
        
        for result in results[:5]:  # Use top 5 results for the answer
            entity_type = result.get("entity_type", "").lower()
            entity_id = result.get("entity_id", "")
            file_path = result.get("file_path", "")
            
            if entity_type and entity_id:
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
                entity_names.add(entity_id)
            
            if file_path:
                file_paths.add(file_path)
        
        # Determine query intent
        intents = query_analysis.get("intents", ["information"])
        primary_intent = intents[0] if intents else "information"
        
        # Generate answer based on intent and results
        if primary_intent == "definition":
            return self._generate_definition_answer(query, results)
        elif primary_intent == "usage":
            return self._generate_usage_answer(query, results)
        elif primary_intent == "inheritance":
            return self._generate_inheritance_answer(query, results)
        elif primary_intent == "explanation":
            return self._generate_explanation_answer(query, results)
        else:
            return self._generate_general_answer(query, results)
    
    def _generate_definition_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate an answer for definition queries.
        
        Args:
            query: Original user query
            results: Ranked search results
            
        Returns:
            Generated answer
        """
        if not results:
            return "I couldn't find any definitions related to your query."
        
        # Find definition results
        definition_results = [r for r in results if r.get("search_type") == "definition"]
        if not definition_results:
            definition_results = results  # Fallback to all results
        
        # Extract the top result
        top_result = definition_results[0]
        entity_type = top_result.get("entity_type", "")
        entity_id = top_result.get("entity_id", "")
        file_path = top_result.get("file_path", "")
        start_line = top_result.get("start_line", 0)
        
        answer = f"I found the definition of `{entity_id}`"
        
        if entity_type:
            answer += f" ({entity_type})"
        
        if file_path:
            answer += f" in `{file_path}`"
            
            if start_line:
                answer += f" at line {start_line}"
        
        # Add information about parameters for functions
        if entity_type == "function" and "parameters" in top_result:
            params = top_result.get("parameters", [])
            if params:
                param_str = ", ".join(params)
                answer += f". It takes parameters: {param_str}"
        
        # Add information about inheritance for classes
        if entity_type == "class" and "parent_class" in top_result:
            parent = top_result.get("parent_class", "")
            if parent:
                answer += f". It extends the `{parent}` class"
        
        if len(definition_results) > 1:
            answer += f". I also found {len(definition_results) - 1} other definitions that might be relevant."
        
        return answer
    
    def _generate_usage_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate an answer for usage queries.
        
        Args:
            query: Original user query
            results: Ranked search results
            
        Returns:
            Generated answer
        """
        if not results:
            return "I couldn't find any usages related to your query."
        
        # Find usage results
        usage_results = [r for r in results if r.get("search_type") == "usage"]
        if not usage_results:
            usage_results = results  # Fallback to all results
        
        # Count callers by type
        caller_types = {}
        for result in usage_results:
            caller_type = result.get("caller_type", "")
            if caller_type:
                caller_types[caller_type] = caller_types.get(caller_type, 0) + 1
        
        # Extract the target entity
        entity_id = usage_results[0].get("entity_id", "")
        entity_type = usage_results[0].get("entity_type", "")
        
        answer = f"I found {len(usage_results)} usages of `{entity_id}`"
        
        if entity_type:
            answer += f" ({entity_type})"
        
        # Add information about caller types
        if caller_types:
            caller_info = []
            for caller_type, count in caller_types.items():
                caller_info.append(f"{count} {caller_type}s")
            
            if caller_info:
                answer += f". It's used by: {', '.join(caller_info)}"
        
        # Add information about specific files
        files = set(r.get("file_path", "") for r in usage_results)
        if len(files) == 1:
            answer += f" in the file `{list(files)[0]}`"
        elif len(files) > 1:
            answer += f" across {len(files)} different files"
        
        return answer
    
    def _generate_inheritance_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate an answer for inheritance queries.
        
        Args:
            query: Original user query
            results: Ranked search results
            
        Returns:
            Generated answer
        """
        if not results:
            return "I couldn't find any inheritance relationships related to your query."
        
        # Find inheritance results
        inheritance_results = [r for r in results if r.get("search_type") == "inheritance"]
        if not inheritance_results:
            inheritance_results = results  # Fallback to all results
        
        # Separate child and parent relationships
        parents = []
        children = []
        
        for result in inheritance_results:
            relationship_type = result.get("relationship_type", "")
            related_entity = result.get("related_entity", "")
            
            if relationship_type == "child" and related_entity:
                parents.append(related_entity)
            elif relationship_type == "parent" and related_entity:
                children.append(related_entity)
        
        # Extract the target entity
        entity_id = inheritance_results[0].get("entity_id", "")
        
        answer = f"I found inheritance relationships for the class `{entity_id}`"
        
        # Add information about parents
        if parents:
            if len(parents) == 1:
                answer += f". It extends the class `{parents[0]}`"
            else:
                parent_list = ", ".join(f"`{p}`" for p in parents)
                answer += f". It extends the classes: {parent_list}"
        
        # Add information about children
        if children:
            if len(children) == 1:
                answer += f". It is extended by the class `{children[0]}`"
            else:
                child_list = ", ".join(f"`{c}`" for c in children)
                answer += f". It is extended by the classes: {child_list}"
        
        if not parents and not children:
            answer += ". It doesn't have any parent or child classes"
        
        return answer
    
    def _generate_explanation_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate an answer for explanation queries.
        
        Args:
            query: Original user query
            results: Ranked search results
            
        Returns:
            Generated answer
        """
        if not results:
            return "I couldn't find any information to explain your query."
        
        # In a real implementation, this would use an LLM to generate explanations
        # based on the code snippets found
        
        # Extract the top entity
        top_result = results[0]
        entity_id = top_result.get("entity_id", "")
        entity_type = top_result.get("entity_type", "")
        file_path = top_result.get("file_path", "")
        
        answer = f"I found information about `{entity_id}`"
        
        if entity_type:
            answer += f" ({entity_type})"
        
        if file_path:
            answer += f" in `{file_path}`"
        
        answer += ".\n\nHere's an explanation of what it does:\n\n"
        
        # Placeholder explanation - in real implementation, this would be generated by an LLM
        answer += f"The {entity_type} `{entity_id}` appears to be responsible for "
        
        if entity_type == "function":
            answer += "processing data and returning a result based on the input parameters."
        elif entity_type == "class":
            answer += "encapsulating related functionality and data into a reusable component."
        elif entity_type == "method":
            answer += "implementing specific behavior for its parent class."
        else:
            answer += "implementing part of the application's functionality."
        
        answer += " You can see the implementation in the code snippets below."
        
        return answer
    
    def _generate_general_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate a general answer for informational queries.
        
        Args:
            query: Original user query
            results: Ranked search results
            
        Returns:
            Generated answer
        """
        if not results:
            return "I couldn't find any information related to your query."
        
        # Count entity types
        entity_counts = {}
        for result in results:
            entity_type = result.get("entity_type", "").lower()
            if entity_type:
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
        
        # Create a summary of the results
        entity_summary = []
        for entity_type, count in entity_counts.items():
            entity_summary.append(f"{count} {entity_type}{'s' if count > 1 else ''}")
        
        # Count file paths
        file_paths = set(r.get("file_path", "") for r in results if r.get("file_path"))
        
        answer = f"I found {len(results)} results related to your query"
        
        if entity_summary:
            answer += f" including {', '.join(entity_summary)}"
        
        if file_paths:
            answer += f" across {len(file_paths)} different files"
        
        # Add information about top result
        top_result = results[0]
        top_entity_id = top_result.get("entity_id", "")
        top_entity_type = top_result.get("entity_type", "")
        top_file_path = top_result.get("file_path", "")
        
        if top_entity_id and top_entity_type:
            answer += f".\n\nThe most relevant result is the {top_entity_type} `{top_entity_id}`"
            
            if top_file_path:
                answer += f" in `{top_file_path}`"
        
        return answer
    
    def _select_code_snippets(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Select the best code snippets to include in the answer.
        
        Args:
            results: Ranked search results
            
        Returns:
            Selected code snippets
        """
        # In a real implementation, this would fetch and format actual code
        # For now, just use the top results
        
        selected = []
        seen_entities = set()
        
        for result in results:
            entity_id = result.get("entity_id", "")
            code_content = result.get("code_content", "")
            file_path = result.get("file_path", "")
            start_line = result.get("start_line", 0)
            end_line = result.get("end_line", 0)
            language = result.get("language", "")
            
            # Skip if no content or duplicate entity
            if not code_content or not entity_id or entity_id in seen_entities:
                continue
                
            seen_entities.add(entity_id)
            
            # Create snippet
            snippet = {
                "entity_id": entity_id,
                "entity_type": result.get("entity_type", ""),
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "language": language,
                "code": code_content,
                "relevance": result.get("rank_score", 0.0)
            }
            
            selected.append(snippet)
            
            # Limit number of snippets
            if len(selected) >= self.max_code_snippets:
                break
        
        return selected
    
    def _count_result_types(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Count results by type.
        
        Args:
            results: Search results
            
        Returns:
            Dictionary with counts by type
        """
        counts = {
            "entity_types": {},
            "search_types": {},
            "sources": {}
        }
        
        for result in results:
            # Count entity types
            entity_type = result.get("entity_type", "").lower()
            if entity_type:
                counts["entity_types"][entity_type] = counts["entity_types"].get(entity_type, 0) + 1
            
            # Count search types
            search_type = result.get("search_type", "").lower()
            if search_type:
                counts["search_types"][search_type] = counts["search_types"].get(search_type, 0) + 1
            
            # Count sources
            source = result.get("source", "").lower()
            if source:
                counts["sources"][source] = counts["sources"].get(source, 0) + 1
        
        return counts
        
    @classmethod
    def build_spec(cls, name: str = "answer_composer_agent") -> AgentSpec:
        """
        Build the agent specification.
        
        Args:
            name: Name of the agent
            
        Returns:
            Agent specification
        """
        return AgentSpec(
            name=name,
            description="Agent responsible for synthesizing search results into coherent answers",
            agent_class=cls,
        )

# Create the agent specification
spec = AnswerComposerAgent.build_spec(name="answer_composer_agent")