"""
Agent Update Template

This is a template for updating agents to use Google ADK directly with proper specs.
"""

from google.adk import Agent, AgentSpec
from google.adk.runtime.context import AgentContext
from google.adk.runtime.responses import HandlerResponse, ToolResponse
from typing import Dict, Any

class ExampleAgent(Agent):
    """Example agent class."""
    
    def __init__(self, name: str, **kwargs):
        """
        Initialize the agent.
        
        Args:
            name: Agent name
            **kwargs: Additional parameters
        """
        super().__init__(name=name)
        self.config = kwargs.get("config", {})
        
    def init(self, context: AgentContext) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Agent context providing access to tools
        """
        self.context = context
    
    def run(self, input_data: Dict[str, Any]) -> HandlerResponse:
        """
        Run the agent.
        
        Args:
            input_data: Input data dictionary
            
        Returns:
            HandlerResponse with results
        """
        return HandlerResponse.success({"message": "Success"})
    
    @classmethod
    def build_spec(cls, name: str) -> AgentSpec:
        """
        Build the agent specification.
        
        Args:
            name: Name of the agent
            
        Returns:
            Agent specification
        """
        return AgentSpec(
            name=name,
            description="Example agent description",
            agent_class=cls,
        )

# Create the agent specification
spec = ExampleAgent.build_spec(name="example_agent")