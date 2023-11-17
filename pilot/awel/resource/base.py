from abc import ABC, abstractmethod


class ResourceGroup(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of current resource group"""
