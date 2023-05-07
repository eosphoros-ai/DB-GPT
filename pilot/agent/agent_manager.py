#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from pilot.singleton import Singleton

class AgentManager(metaclass=Singleton):
    """Agent manager for managing DB-GPT agents"""
    def __init__(self) -> None:
        
        self.agents = {} #TODO need to define

    def create_agent(self):
        pass

    def message_agent(self):
        pass

    def list_agents(self):
        pass

    def delete_agent(self):
        pass

