"""LLM module."""

import logging
from collections import defaultdict
from typing import Dict, Optional, Type, cast

from dbgpt import BaseComponent
from dbgpt.component import ComponentType, SystemApp
from dbgpt.core import ModelRequest

from .strategy.base import LLMStrategyType
from .strategy.default import LLMStrategy

logger = logging.getLogger(__name__)


def _build_model_request(input_value: Dict) -> ModelRequest:
    """Build model request from input value.

    Args:
        input_value(str or dict): input value

    Returns:
        ModelRequest: model request, pass to llm client
    """
    parm = {
        "model": input_value.get("model"),
        "messages": input_value.get("messages"),
        "temperature": input_value.get("temperature", None),
        "max_new_tokens": input_value.get("max_new_tokens", None),
        "stop": input_value.get("stop", None),
        "stop_token_ids": input_value.get("stop_token_ids", None),
        "context_len": input_value.get("context_len", None),
        "echo": input_value.get("echo", None),
        "span_id": input_value.get("span_id", None),
    }

    return ModelRequest(**parm)


class LLMStrategyManager(BaseComponent):
    """Manages the registration and retrieval of agents."""

    name = ComponentType.LLM_STRATEGY_MANAGER

    def __init__(self, system_app: SystemApp):
        """Create a new AgentManager."""
        super().__init__(system_app)
        self.system_app = system_app
        self._llm_strategys: Dict[LLMStrategyType, Type[LLMStrategy]] = defaultdict()

    def init_app(self, system_app: SystemApp):
        """Initialize the LLM Strategy Manager."""
        self.system_app = system_app

    def after_start(self):
        """Register all llm_strategy."""
        llm_strategies = scan_llm_strategy()
        for _, llm_strategies in llm_strategies.items():
            self.register_llm_strategy_cls(llm_strategies.type(), llm_strategies)

    def register_llm_strategy_cls(
        self, llm_strategy_type: LLMStrategyType, strategy: Type[LLMStrategy]
    ):
        """Register llm strategy."""
        self._llm_strategys[llm_strategy_type] = strategy

    def get_llm_strategy_cls(
        self,
        llm_strategy_type: LLMStrategyType,
    ) -> Optional[Type[LLMStrategy]]:
        return self._llm_strategys.get(llm_strategy_type, None)


_HAS_SCAN = False


def scan_llm_strategy():
    """Scan and register all agents."""
    from dbgpt.util.module_utils import ModelScanner, ScannerConfig

    global _HAS_SCAN

    if _HAS_SCAN:
        return
    scanner = ModelScanner[LLMStrategy]()
    for path in ["dbgpt.agent.util.llm.strategy", "dbgpt_ext.agent.llm.strategy"]:
        config = ScannerConfig(
            module_path=path,
            base_class=LLMStrategy,
            recursive=True,
        )
        scanner.scan_and_register(config)
    _HAS_SCAN = True
    return scanner.get_registered_items()


_SYSTEM_APP: Optional[SystemApp] = None


def initialize_llm_strategy_manager(system_app: SystemApp):
    """Initialize the llm strategy manager."""
    global _SYSTEM_APP
    _SYSTEM_APP = system_app
    llm_strategy_manager = LLMStrategyManager(system_app)
    system_app.register_instance(llm_strategy_manager)


def get_llm_strategy_manager(
    system_app: Optional[SystemApp] = None,
) -> LLMStrategyManager:
    """Return the  llm strategy manager.

    Args:
        system_app (Optional[SystemApp], optional): The system app. Defaults to None.

    Returns:
        LLMStrategyManager: The llm strategy manager.
    """
    if not _SYSTEM_APP:
        if not system_app:
            system_app = SystemApp()
        initialize_llm_strategy_manager(system_app)
    app = system_app or _SYSTEM_APP
    return LLMStrategyManager.get_instance(cast(SystemApp, app))
