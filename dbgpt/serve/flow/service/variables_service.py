from typing import List, Optional

from dbgpt import SystemApp
from dbgpt.core.interface.variables import (
    BUILTIN_VARIABLES_CORE_AGENTS,
    BUILTIN_VARIABLES_CORE_DATASOURCES,
    BUILTIN_VARIABLES_CORE_EMBEDDINGS,
    BUILTIN_VARIABLES_CORE_FLOW_NODES,
    BUILTIN_VARIABLES_CORE_FLOWS,
    BUILTIN_VARIABLES_CORE_KNOWLEDGE_SPACES,
    BUILTIN_VARIABLES_CORE_LLMS,
    BUILTIN_VARIABLES_CORE_RERANKERS,
    BUILTIN_VARIABLES_CORE_SECRETS,
    BUILTIN_VARIABLES_CORE_VARIABLES,
    StorageVariables,
    VariablesProvider,
)
from dbgpt.serve.core import BaseService, blocking_func_to_async
from dbgpt.util import PaginationResult
from dbgpt.util.i18n_utils import _

from ..api.schemas import VariablesKeyResponse, VariablesRequest, VariablesResponse
from ..config import (
    SERVE_CONFIG_KEY_PREFIX,
    SERVE_VARIABLES_SERVICE_COMPONENT_NAME,
    ServeConfig,
)
from ..models.models import VariablesDao, VariablesEntity

BUILTIN_VARIABLES = [
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_FLOWS,
        label=_("All AWEL Flows"),
        description=_("Fetch all AWEL flows in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_FLOW_NODES,
        label=_("All AWEL Flow Nodes"),
        description=_("Fetch all AWEL flow nodes in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_VARIABLES,
        label=_("All Variables"),
        description=_("Fetch all variables in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_SECRETS,
        label=_("All Secrets"),
        description=_("Fetch all secrets in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_LLMS,
        label=_("All LLMs"),
        description=_("Fetch all LLMs in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_EMBEDDINGS,
        label=_("All Embeddings"),
        description=_("Fetch all embeddings models in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_RERANKERS,
        label=_("All Rerankers"),
        description=_("Fetch all rerankers in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_DATASOURCES,
        label=_("All Data Sources"),
        description=_("Fetch all data sources in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_AGENTS,
        label=_("All Agents"),
        description=_("Fetch all agents in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
    VariablesKeyResponse(
        key=BUILTIN_VARIABLES_CORE_KNOWLEDGE_SPACES,
        label=_("All Knowledge Spaces"),
        description=_("Fetch all knowledge spaces in the system"),
        value_type="str",
        category="common",
        scope="global",
    ),
]


def _is_builtin_variable(key: str) -> bool:
    return key in [v.key for v in BUILTIN_VARIABLES]


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
        """List all variables.

        Please note that this method will return all variables in the system, it may
        be a large list.
        """
        return self.dao.get_list({"enabled": True, "category": category})

    def list_keys(
        self,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[VariablesKeyResponse]:
        """List all keys."""
        results = []

        # TODO: More high performance way to get the keys
        all_db_variables = self.dao.get_list(
            {
                "enabled": True,
                "category": category,
                "user_name": user_name,
                "sys_code": sys_code,
            }
        )
        if not user_name:
            # Only return the keys that are not user specific
            all_db_variables = [v for v in all_db_variables if not v.user_name]
        if not sys_code:
            # Only return the keys that are not system specific
            all_db_variables = [v for v in all_db_variables if not v.sys_code]
        key_to_db_variable = {}
        for db_variable in all_db_variables:
            key = db_variable.key
            if key not in key_to_db_variable:
                key_to_db_variable[key] = db_variable

        # Append all builtin variables to the results
        results.extend(BUILTIN_VARIABLES)

        # Append all db variables to the results
        for key, db_variable in key_to_db_variable.items():
            results.append(
                VariablesKeyResponse(
                    key=key,
                    label=db_variable.label,
                    description=db_variable.description,
                    value_type=db_variable.value_type,
                    category=db_variable.category,
                    scope=db_variable.scope,
                    scope_key=db_variable.scope_key,
                )
            )
        return results

    async def get_list_by_page(
        self,
        key: str,
        scope: Optional[str] = None,
        scope_key: Optional[str] = None,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginationResult[VariablesResponse]:
        """Get a list of variables by page."""
        if not _is_builtin_variable(key):
            query = {
                "key": key,
                "scope": scope,
                "scope_key": scope_key,
                "user_name": user_name,
                "sys_code": sys_code,
            }
            return await blocking_func_to_async(
                self._system_app,
                self.dao.get_list_page,
                query,
                page,
                page_size,
                desc_order_column="gmt_modified",
            )
        else:
            variables: List[
                StorageVariables
            ] = await self.variables_provider.async_get_variables(
                key=key,
                scope=scope,
                scope_key=scope_key,
                sys_code=sys_code,
                user_name=user_name,
            )
            result_variables = []
            for entity in variables:
                result_variables.append(
                    VariablesResponse(
                        id=-1,
                        key=entity.key,
                        name=entity.name,
                        label=entity.label,
                        value=entity.value,
                        value_type=entity.value_type,
                        category=entity.category,
                        scope=entity.scope,
                        scope_key=entity.scope_key,
                        enabled=True if entity.enabled == 1 else False,
                        user_name=entity.user_name,
                        sys_code=entity.sys_code,
                        description=entity.description,
                    )
                )
            return PaginationResult.build_from_all(
                result_variables,
                page,
                page_size,
            )
