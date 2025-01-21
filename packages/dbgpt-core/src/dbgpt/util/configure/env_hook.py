"""Hooks for setting environment variables."""

import os
from typing import Any, Dict, List, Optional


class EnvVarSetHook:
    """A hook that sets environment variables based on initialization parameters"""

    def __init__(self, env_vars: Optional[List[Dict[str, str]]] = None):
        """
        Args:
            env_vars: Dictionary of environment variables to set.
                     Key is the environment variable name, value is its value.
        """
        env_kv = {}
        for env_var in env_vars or []:
            if not isinstance(env_var, dict):
                raise ValueError(
                    f"Expected env_vars to be a list of dictionaries, got {env_var}"
                )
            if not env_var:
                raise ValueError("Expected env_var to be a non-empty dictionary")
            env_key = env_var.get("key")
            env_value = env_var.get("value")
            env_kv[env_key] = env_value
        self.env_vars = env_kv
        self._original_env = {}

    def __call__(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Set environment variables and return the config unchanged."""
        # Save original environment variables that we're going to override
        self._original_env = {
            key: os.environ.get(key) for key in self.env_vars if key in os.environ
        }

        # Set new environment variables
        for key, value in self.env_vars.items():
            os.environ[key] = str(value)

        return config
