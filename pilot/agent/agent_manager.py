#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from pilot.singleton import Singleton
from pilot.configs.config import Config
from typing import List
from pilot.model.base import Message

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
        messages: List[Message] = [
            {"role": "user", "content": prompt}, 
        ] 

        for plugin in self.cfg.plugins:
            if not plugin.can_handle_pre_instruction():
                continue
            if plugin_messages := plugin.pre_instruction(messages):
                messages.extend(iter(plugin_messages))
            # 

    def message_agent(self):
        pass

    def list_agents(self):
        pass

    def delete_agent(self):
        pass

