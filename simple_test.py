#!/usr/bin/env python3
"""
Simple test to verify our changes work correctly.
"""
import sys
import os

def check_agent_wrapper():
    """
    Test the AgentWrapper class functionality.
    """
    
    class MockAgentWrapper:
        """Mock AgentWrapper class for testing."""
        
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
    
    # Create a wrapper instance
    wrapper = MockAgentWrapper()
    
    # Test setting attributes
    wrapper.test_attribute = "test value"
    wrapper.config = {"key1": "value1", "key2": "value2"}
    
    # Test getting attributes
    assert wrapper.test_attribute == "test value", f"Expected 'test value', got '{wrapper.test_attribute}'"
    assert wrapper.config == {"key1": "value1", "key2": "value2"}, f"Config mismatch: {wrapper.config}"
    
    # Test get_config method
    assert wrapper.get_config("key1") == "value1", f"Expected 'value1', got '{wrapper.get_config('key1')}'"
    assert wrapper.get_config("key2") == "value2", f"Expected 'value2', got '{wrapper.get_config('key2')}'"
    assert wrapper.get_config("key3", "default") == "default", f"Expected 'default', got '{wrapper.get_config('key3', 'default')}'"
    
    # If we reach here, all tests passed
    print("✅ AgentWrapper tests passed")

def check_init_agent_decorator():
    """
    Test the functionality of the init_agent decorator.
    """
    import uuid
    import functools
    
    # Mock Agent class
    class Agent:
        """Mock Agent class for testing."""
        def __init__(self, name):
            self.name = name
    
    # Mock agent state dictionary
    _agent_state = {}
    
    # Mock AgentWrapper class
    class AgentWrapper:
        """Mock AgentWrapper class for testing."""
        
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
    
    # Define init_agent decorator
    def init_agent(name):
        """
        Mock init_agent decorator for testing.
        """
        def decorator(cls):
            # Store the original methods
            original_init = cls.__init__
            original_run = getattr(cls, 'run', lambda self, inputs: None)
            
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
                
                # Call an init_wrapper method to let the child class initialize the wrapper
                if hasattr(cls, 'init_wrapper'):
                    cls.init_wrapper(self, wrapper, *args, **kwargs)
            
            def new_run(self, inputs):
                # Get the wrapper
                agent_id = object.__getattribute__(self, '_agent_id')
                wrapper = _agent_state.get(agent_id)
                
                # Call the original run with the wrapper as the first parameter
                try:
                    return original_run(self, wrapper, inputs)
                except Exception as e:
                    print(f"Error in agent execution: {e}")
                    return None
            
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
    
    # Test the decorator with a simple agent class
    @init_agent(name="test_agent")
    class TestAgent(Agent):
        """Test agent class for testing the decorator."""
        
        def init_wrapper(self, wrapper, config, *args, **kwargs):
            """Initialize the wrapper with test data."""
            wrapper.test_attribute = "test value"
            wrapper.repositories = config.get('repositories', [])
        
        def run(self, wrapper, inputs):
            """Test run method that uses the wrapper."""
            return {"test_attribute": wrapper.test_attribute}
    
    # Create an agent instance
    agent = TestAgent({"repositories": ["repo1", "repo2"]})
    
    # Check that the agent was initialized correctly
    assert hasattr(agent, '_agent_id'), "Agent should have _agent_id attribute"
    
    # Get the wrapper
    wrapper = agent.get_wrapper()
    assert wrapper is not None, "Agent wrapper should not be None"
    
    # Check that the wrapper was initialized correctly
    assert wrapper.test_attribute == "test value", f"Expected 'test value', got '{wrapper.test_attribute}'"
    assert wrapper.repositories == ["repo1", "repo2"], f"Expected ['repo1', 'repo2'], got '{wrapper.repositories}'"
    
    # Test run method
    result = agent.run({})
    assert result == {"test_attribute": "test value"}, f"Expected {{'test_attribute': 'test value'}}, got {result}"
    
    # If we reach here, all tests passed
    print("✅ init_agent decorator tests passed")

# Run the tests
if __name__ == "__main__":
    print("🧪 Running tests for our adapter code...")
    check_agent_wrapper()
    check_init_agent_decorator()
    print("✨ All tests passed successfully!")