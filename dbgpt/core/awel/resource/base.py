"""Base class for resource group."""
from abc import ABC, abstractmethod


class ResourceGroup(ABC):
    """Base class for resource group.

    A resource group is a group of resources that are related to each other.
    It contains the all resources that are needed to run a workflow.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of current resource group."""
