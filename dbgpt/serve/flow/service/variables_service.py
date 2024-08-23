from typing import List, Optional

from dbgpt import SystemApp
from dbgpt.core.interface.variables import StorageVariables, VariablesProvider
from dbgpt.serve.core import BaseService

from ..api.schemas import VariablesRequest, VariablesResponse
from ..config import (
    SERVE_CONFIG_KEY_PREFIX,
    SERVE_VARIABLES_SERVICE_COMPONENT_NAME,
    ServeConfig,
)
from ..models.models import VariablesDao, VariablesEntity


class VariablesService(
    BaseService[VariablesEntity, VariablesRequest, VariablesResponse]
):
    """Variables service"""

    name = SERVE_VARIABLES_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, dao: Optional[VariablesDao] = None):
        self._system_app = None
        self._serve_config: ServeConfig = None
        self._dao: VariablesDao = dao

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        super().init_app(system_app)

        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or VariablesDao(self._serve_config)
        self._system_app = system_app

    @property
    def dao(self) -> VariablesDao:
        """Returns the internal DAO."""
        return self._dao

    @property
    def variables_provider(self) -> VariablesProvider:
        """Returns the internal VariablesProvider.

        Returns:
            VariablesProvider: The internal VariablesProvider
        """
        variables_provider = VariablesProvider.get_instance(
            self._system_app, default_component=None
        )
        if variables_provider:
            return variables_provider
        else:
            from ..serve import Serve

            variables_provider = Serve.get_instance(self._system_app).variables_provider
            self._system_app.register_instance(variables_provider)
            return variables_provider

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    def create(self, request: VariablesRequest) -> VariablesResponse:
        """Create a new entity

        Args:
            request (VariablesRequest): The request

        Returns:
            VariablesResponse: The response
        """
        variables = StorageVariables(
            key=request.key,
            name=request.name,
            label=request.label,
            value=request.value,
            value_type=request.value_type,
            category=request.category,
            scope=request.scope,
            scope_key=request.scope_key,
            user_name=request.user_name,
            sys_code=request.sys_code,
            enabled=1 if request.enabled else 0,
            description=request.description,
        )
        self.variables_provider.save(variables)
        query = {
            "key": request.key,
            "name": request.name,
            "scope": request.scope,
            "scope_key": request.scope_key,
            "sys_code": request.sys_code,
            "user_name": request.user_name,
            "enabled": request.enabled,
        }
        return self.dao.get_one(query)

    def update(self, _: int, request: VariablesRequest) -> VariablesResponse:
        """Update variables.

        Args:
            request (VariablesRequest): The request

        Returns:
            VariablesResponse: The response
        """
        variables = StorageVariables(
            key=request.key,
            name=request.name,
            label=request.label,
            value=request.value,
            value_type=request.value_type,
            category=request.category,
            scope=request.scope,
            scope_key=request.scope_key,
            user_name=request.user_name,
            sys_code=request.sys_code,
            enabled=1 if request.enabled else 0,
            description=request.description,
        )
        exist_value = self.variables_provider.get(
            variables.identifier.str_identifier, None
        )
        if exist_value is None:
            raise ValueError(
                f"Variable {variables.identifier.str_identifier} not found"
            )
        self.variables_provider.save(variables)
        query = {
            "key": request.key,
            "name": request.name,
            "scope": request.scope,
            "scope_key": request.scope_key,
            "sys_code": request.sys_code,
            "user_name": request.user_name,
            "enabled": request.enabled,
        }
        return self.dao.get_one(query)

    def list_all_variables(self, category: str = "common") -> List[VariablesResponse]:
        """List all variables."""
        return self.dao.get_list({"enabled": True, "category": category})
