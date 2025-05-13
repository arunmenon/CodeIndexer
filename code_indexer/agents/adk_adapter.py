"""
ADK Adapter Module

This module provides adapters for the latest Google Agent Development Kit (ADK).
It takes care of proper initialization of agents with name parameters and other requirements.
"""

import logging
import functools
import inspect
import uuid
import types
from typing import Dict, Any, Type, Optional, TypeVar, Callable, Union, List, Tuple

# Import directly from the latest ADK
from google.adk import Agent
from google.adk.tools.google_api_tool import AgentContext, HandlerResponse, ToolResponse
from google.adk.tools.google_api_tool import ToolStatus

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Agent)

# Dictionary to store agent state by ID
_agent_state = {}

# Create a custom wrapper class for Agent that can hold arbitrary attributes
class AgentWrapper:
    """
    A wrapper that holds attributes for an Agent instance.
    
    Since Agent is a Pydantic model with strict field validation,
    we use this wrapper to store additional attributes that the agent
    needs to function.
    """
    def __init__(self):
        self._attrs = {}
        
    def __getattr__(self, name):
        if name in self._attrs:
            return self._attrs[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        
    def __setattr__(self, name, value):
        if name == '_attrs':
            super().__setattr__(name, value)
        else:
            self._attrs[name] = value
            
    def get_config(self, key, default=None):
        """Get a configuration value."""
        config = self._attrs.get('config', {})
        return config.get(key, default)

def init_agent(name: str) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator for Agent classes that handles initialization with the required name parameter.
    
    Args:
        name: The name to use for this agent
        
    Returns:
        A decorator function
    """
    def decorator(cls: Type[T]) -> Type[T]:
        # Store the original methods
        original_init = cls.__init__
        original_run = cls.run
        
        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Initialize the Agent base class with the name
            super(cls, self).__init__(name=name)
            
            # Generate a unique ID for this instance and store it
            agent_id = str(uuid.uuid4())
            
            # Create a wrapper and store it
            wrapper = AgentWrapper()
            _agent_state[agent_id] = wrapper
            
            # Save reference to the ID
            object.__setattr__(self, '_agent_id', agent_id)
            
            # Extract configuration
            config_dict = {}
            if args and isinstance(args[0], dict):
                config_dict = args[0]
            elif 'config' in kwargs and isinstance(kwargs['config'], dict):
                config_dict = kwargs['config']
                
            # Store configuration in wrapper
            wrapper.config = config_dict
            
            # Create a logger and store in wrapper
            wrapper.logger = logging.getLogger(name)
            
            # Call an init_wrapper method to let the child class initialize the wrapper
            # This avoids issues with setting attributes directly on the Agent instance
            if hasattr(cls, 'init_wrapper'):
                cls.init_wrapper(self, wrapper, *args, **kwargs)
            
        @functools.wraps(original_run)
        def new_run(self, inputs: Dict[str, Any]) -> HandlerResponse:
            # Get the wrapper
            agent_id = object.__getattribute__(self, '_agent_id')
            wrapper = _agent_state.get(agent_id)
            
            # Call the original run with the wrapper as the first parameter
            try:
                return original_run(self, wrapper, inputs)
            except Exception as e:
                logger.error(f"Error in agent execution: {e}")
                return HandlerResponse.error(f"Error in agent execution: {e}")
            
        # Replace methods
        cls.__init__ = new_init
        cls.run = new_run
        
        # Add a method to get the wrapper for an agent instance
        def get_wrapper(self):
            """Get the wrapper for this agent instance."""
            agent_id = object.__getattribute__(self, '_agent_id')
            return _agent_state.get(agent_id)
        
        cls.get_wrapper = get_wrapper
        
        return cls
    
    return decorator

# Add helpers to interact with agent wrappers
def get_wrapper(agent_instance):
    """Get the wrapper for an agent instance."""
    agent_id = object.__getattribute__(agent_instance, '_agent_id')
    return _agent_state.get(agent_id)

def get_config(agent_instance, key, default=None):
    """Get a configuration value for an agent instance."""
    wrapper = get_wrapper(agent_instance)
    if wrapper:
        return wrapper.get_config(key, default)
    return default

# Export the necessary classes
__all__ = ['Agent', 'AgentContext', 'HandlerResponse', 'ToolResponse', 'ToolStatus', 
           'init_agent', 'get_wrapper', 'get_config', 'AgentWrapper']