"""
ADK Compatibility Layer

Provides compatibility between different versions of Google's Agent Development Kit.
This file monkey patches the Agent class to ensure that our code can work with both
the old and new versions of the ADK.
"""

import logging
import importlib
import sys
from typing import Dict, Any, Optional, List, Union, Callable

logger = logging.getLogger(__name__)

# First, determine which version of the ADK we are using
try:
    from google.adk import Agent as NewAgent
    # Import other needed classes
    from google.adk.tools.google_api_tool import AgentContext as NewAgentContext
    from google.adk.tools.google_api_tool import HandlerResponse as NewHandlerResponse
    from google.adk.tools.google_api_tool import ToolResponse as NewToolResponse
    # We're using the new ADK
    HAS_NEW_ADK = True
    logger.info("Using new ADK version")
except ImportError:
    try:
        # Try to import old ADK classes
        from google.adk.api.agent import Agent as OldAgent
        from google.adk.api.agent import AgentContext as OldAgentContext
        from google.adk.api.agent import HandlerResponse as OldHandlerResponse
        from google.adk.api.tool import ToolResponse as OldToolResponse
        # We're using the old ADK
        HAS_NEW_ADK = False
        logger.info("Using old ADK version")
    except ImportError:
        # No ADK available
        logger.error("No ADK version available")
        raise ImportError("No ADK version found")

# Monkey patch to create compatibility
if HAS_NEW_ADK:
    # New ADK uses Pydantic, so we need to create a compatible class
    # that adheres to its initialization rules but behaves like our
    # existing agent classes

    # Store the original NewAgent.__init__ so we can call it
    original_new_agent_init = NewAgent.__init__

    # Define a new __init__ for NewAgent that allows our classes to work properly
    def compatible_new_agent_init(self, *args, **kwargs):
        # First, call the original init with just the name
        name = kwargs.get('name', self.__class__.__name__.lower())
        original_new_agent_init(self, name=name)
        
        # Now handle any other state manually to avoid Pydantic validation
        for key, value in kwargs.items():
            if key != 'name':
                object.__setattr__(self, key, value)

    # Replace the original __init__ with our compatible version
    NewAgent.__init__ = compatible_new_agent_init

    # Export the classes
    Agent = NewAgent
    AgentContext = NewAgentContext
    HandlerResponse = NewHandlerResponse
    ToolResponse = NewToolResponse
else:
    # For the old ADK, we can just use the classes directly
    Agent = OldAgent
    AgentContext = OldAgentContext
    HandlerResponse = OldHandlerResponse
    ToolResponse = OldToolResponse

# Add any other compatibility functions or classes below
def get_handler_response_class():
    """Get the appropriate HandlerResponse class."""
    return HandlerResponse

def create_error_response(message: str) -> HandlerResponse:
    """Create an error response in a cross-ADK compatible way."""
    return HandlerResponse.error(message)

def create_success_response(data: Dict[str, Any]) -> HandlerResponse:
    """Create a success response in a cross-ADK compatible way."""
    return HandlerResponse.success(data)