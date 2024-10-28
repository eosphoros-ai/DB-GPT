from typing import List, Literal, Optional

from dbgpt.core.interface.variables import (
    BUILTIN_VARIABLES_CORE_AGENTS,
    BUILTIN_VARIABLES_CORE_DATASOURCES,
    BUILTIN_VARIABLES_CORE_EMBEDDINGS,
    BUILTIN_VARIABLES_CORE_FLOW_NODES,
    BUILTIN_VARIABLES_CORE_FLOWS,
    BUILTIN_VARIABLES_CORE_KNOWLEDGE_SPACES,
    BUILTIN_VARIABLES_CORE_LLMS,
    BUILTIN_VARIABLES_CORE_SECRETS,
    BUILTIN_VARIABLES_CORE_VARIABLES,
    BuiltinVariablesProvider,
    StorageVariables,
)

from ..service.service import Service
from .endpoints import get_service, get_variable_service
from .schemas import ServerResponse


class BuiltinFlowVariablesProvider(BuiltinVariablesProvider):
    """Builtin flow variables provider.

    Provide all flows by variables "${dbgpt.core.flow.flows}"
    """

    name = BUILTIN_VARIABLES_CORE_FLOWS

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        service: Service = get_service()
        page_result = service.get_list_by_page(
            {
                "user_name": user_name,
                "sys_code": sys_code,
            },
            1,
            1000,
        )
        flows: List[ServerResponse] = page_result.items
        variables = []
        for flow in flows:
            variables.append(
                StorageVariables(
                    key=key,
                    name=flow.name,
                    label=flow.label,
                    value=flow.uid,
                    scope=scope,
                    scope_key=scope_key,
                    sys_code=sys_code,
                    user_name=user_name,
                    description=flow.description,
                )
            )
        return variables


class BuiltinNodeVariablesProvider(BuiltinVariablesProvider):
    """Builtin node variables provider.

    Provide all nodes by variables "${dbgpt.core.flow.nodes}"
    """

    name = BUILTIN_VARIABLES_CORE_FLOW_NODES

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        from dbgpt.core.awel.flow.base import _OPERATOR_REGISTRY

        metadata_list = _OPERATOR_REGISTRY.metadata_list()
        variables = []
        for metadata in metadata_list:
            variables.append(
                StorageVariables(
                    key=key,
                    name=metadata["name"],
                    label=metadata["label"],
                    value=metadata["id"],
                    scope=scope,
                    scope_key=scope_key,
                    sys_code=sys_code,
                    user_name=user_name,
                    description=metadata.get("description"),
                )
            )
        return variables


class BuiltinAllVariablesProvider(BuiltinVariablesProvider):
    """Builtin all variables provider.

    Provide all variables by variables "${dbgpt.core.variables}"
    """

    name = BUILTIN_VARIABLES_CORE_VARIABLES

    def _get_variables_from_db(
        self,
        key: str,
        scope: str,
        scope_key: Optional[str],
        sys_code: Optional[str],
        user_name: Optional[str],
        category: Literal["common", "secret"] = "common",
    ) -> List[StorageVariables]:
        storage_variables = get_variable_service().list_all_variables(category)
        variables = []
        for var in storage_variables:
            variables.append(
                StorageVariables(
                    key=key,
                    name=var.name,
                    label=var.label,
                    value=var.value,
                    category=var.category,
                    value_type=var.value_type,
                    scope=scope,
                    scope_key=scope_key,
                    sys_code=sys_code,
                    user_name=user_name,
                    enabled=1 if var.enabled else 0,
                    description=var.description,
                )
            )
        return variables

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables.

        TODO: Return all builtin variables
        """
        return self._get_variables_from_db(key, scope, scope_key, sys_code, user_name)


class BuiltinAllSecretVariablesProvider(BuiltinAllVariablesProvider):
    """Builtin all secret variables provider.

    Provide all secret variables by variables "${dbgpt.core.secrets}"
    """

    name = BUILTIN_VARIABLES_CORE_SECRETS

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        return self._get_variables_from_db(
            key, scope, scope_key, sys_code, user_name, "secret"
        )


class BuiltinLLMVariablesProvider(BuiltinVariablesProvider):
    """Builtin LLM variables provider.

    Provide all LLM variables by variables "${dbgpt.core.llmv}"
    """

    name = BUILTIN_VARIABLES_CORE_LLMS

    def support_async(self) -> bool:
        """Whether the dynamic options support async."""
        return True

    async def _get_models(
        self,
        key: str,
        scope: str,
        scope_key: Optional[str],
        sys_code: Optional[str],
        user_name: Optional[str],
        expect_worker_type: str = "llm",
    ) -> List[StorageVariables]:
        from dbgpt.model.cluster.controller.controller import BaseModelController

        controller = BaseModelController.get_instance(self.system_app)
        models = await controller.get_all_instances(healthy_only=True)
        model_dict = {}
        for model in models:
            worker_name, worker_type = model.model_name.split("@")
            if expect_worker_type == worker_type:
                model_dict[worker_name] = model
        variables = []
        for worker_name, model in model_dict.items():
            variables.append(
                StorageVariables(
                    key=key,
                    name=worker_name,
                    label=worker_name,
                    value=worker_name,
                    scope=scope,
                    scope_key=scope_key,
                    sys_code=sys_code,
                    user_name=user_name,
                )
            )
        return variables

    async def async_get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        return await self._get_models(key, scope, scope_key, sys_code, user_name)

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        raise NotImplementedError(
            "Not implemented get variables sync, please use async_get_variables"
        )


class BuiltinEmbeddingsVariablesProvider(BuiltinLLMVariablesProvider):
    """Builtin embeddings variables provider.

    Provide all embeddings variables by variables "${dbgpt.core.embeddings}"
    """

    name = BUILTIN_VARIABLES_CORE_EMBEDDINGS

    async def async_get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        return await self._get_models(
            key, scope, scope_key, sys_code, user_name, "text2vec"
        )


class BuiltinDatasourceVariablesProvider(BuiltinVariablesProvider):
    """Builtin datasource variables provider.

    Provide all datasource variables by variables "${dbgpt.core.datasource}"
    """

    name = BUILTIN_VARIABLES_CORE_DATASOURCES

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        from dbgpt.serve.datasource.service.service import (
            DatasourceServeResponse,
            Service,
        )

        all_datasource: List[DatasourceServeResponse] = Service.get_instance(
            self.system_app
        ).list()

        variables = []
        for datasource in all_datasource:
            label = f"[{datasource.db_type}]{datasource.db_name}"
            variables.append(
                StorageVariables(
                    key=key,
                    name=datasource.db_name,
                    label=label,
                    value=datasource.db_name,
                    scope=scope,
                    scope_key=scope_key,
                    sys_code=sys_code,
                    user_name=user_name,
                    description=datasource.comment,
                )
            )
        return variables


class BuiltinAgentsVariablesProvider(BuiltinVariablesProvider):
    """Builtin agents variables provider.

    Provide all agents variables by variables "${dbgpt.core.agent.agents}"
    """

    name = BUILTIN_VARIABLES_CORE_AGENTS

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        from dbgpt.agent.core.agent_manage import get_agent_manager

        agent_manager = get_agent_manager(self.system_app)
        agents = agent_manager.list_agents()
        variables = []
        for agent in agents:
            variables.append(
                StorageVariables(
                    key=key,
                    name=agent["name"],
                    label=agent["name"],
                    value=agent["name"],
                    scope=scope,
                    scope_key=scope_key,
                    sys_code=sys_code,
                    user_name=user_name,
                    description=agent["desc"],
                )
            )
        return variables


class BuiltinKnowledgeSpacesVariablesProvider(BuiltinVariablesProvider):
    """Builtin knowledge variables provider.

    Provide all knowledge variables by variables "${dbgpt.core.knowledge_spaces}"
    """

    name = BUILTIN_VARIABLES_CORE_KNOWLEDGE_SPACES

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get the builtin variables."""
        from dbgpt.serve.rag.service.service import Service, SpaceServeRequest

        # TODO: Query with user_name and sys_code
        knowledge_list = Service.get_instance(self.system_app).get_list(
            SpaceServeRequest()
        )
        variables = []
        for k in knowledge_list:
            variables.append(
                StorageVariables(
                    key=key,
                    name=k.name,
                    label=k.name,
                    value=k.name,
                    scope=scope,
                    scope_key=scope_key,
                    sys_code=sys_code,
                    user_name=user_name,
                    description=k.desc,
                )
            )
        return variables
