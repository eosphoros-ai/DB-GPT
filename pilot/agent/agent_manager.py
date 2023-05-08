#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from pilot.singleton import Singleton
from pilot.configs.config import Config

class AgentManager(metaclass=Singleton):
    """Agent manager for managing DB-GPT agents
       In order to compatible auto gpt plugins, 
       we use the same template with it.
    
        Args: next_keys
                agents
                cfg
    """

    def __init__(self) -> None:
        self.next_key = 0
        self.agents = {} #TODO need to define
        self.cfg = Config()

    def create_agent(self, task: str, prompt: str, model: str) -> tuple[int, str]:
        """Create a new agent and return its key
    
        Args:
            task: The task to perform
            prompt: The prompt to use
            model: The model to use

        Returns:
            The key of the new agent
        """
        pass

    def message_agent(self):
        pass

    def list_agents(self):
        pass

    def delete_agent(self):
        pass

