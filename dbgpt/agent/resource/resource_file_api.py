from typing import Any, Dict, List, Optional, Tuple, Union

from .resource_api import ResourceClient, ResourceType


class ResourceFileClient(ResourceClient):
    @property
    def type(self) -> ResourceType:
        return ResourceType.File
