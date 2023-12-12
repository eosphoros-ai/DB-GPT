from __future__ import annotations
import os
import sys
import asyncio
from typing import List, Optional, Dict, Callable
import logging
import diskcache
import json
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.core.awel import BaseOperator, SimpleCallDataInputSource, InputOperator, DAG
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.tracer import root_tracer, trace
from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt.model.operator.model_operator import ModelOperator, ModelStreamOperator

from dbgpt.component import ComponentType, SystemApp
from dbgpt._private.config import Config

logger = logging.getLogger(__name__)
CFG = Config()


class AIWrapper:
    cache_path_root: str = ".cache"
    extra_kwargs = {"cache_seed", "filter_func", "allow_format_str_template", "context", "llm_model"}
    def __init__(self):
        self._executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()
        self._model_operator: BaseOperator = self._build_model_operator()
        self._model_stream_operator: BaseOperator = self._build_model_operator(
            is_stream=True, dag_name="llm_stream_model_dag"
        )
        self.llm_echo = False
        self.sep = "###" ###TODO
        self.model_cache_enable= False
        self.out_parser = BaseOutputParser(sep= self.sep, is_stream_out=False) ###TODO


    @classmethod
    def instantiate(
        cls,
        template: str | Callable | None,
        context: Optional[Dict] = None,
        allow_format_str_template: Optional[bool] = False,
    ):
        if not context or template is None:
            return template
        if isinstance(template, str):
            return template.format(**context) if allow_format_str_template else template
        return template(context)

    def _construct_create_params(self, create_config: Dict, extra_kwargs: Dict) -> Dict:
        """Prime the create_config with additional_kwargs."""
        # Validate the config
        prompt = create_config.get("prompt")
        messages = create_config.get("messages")
        if (prompt is None) == (messages is None):
            raise ValueError("Either prompt or messages should be in create config but not both.")

        context = extra_kwargs.get("context")
        if context is None:
            # No need to instantiate if no context is provided.
            return create_config
        # Instantiate the prompt or messages
        allow_format_str_template = extra_kwargs.get("allow_format_str_template", False)
        # Make a copy of the config
        params = create_config.copy()
        if prompt is not None:
            # Instantiate the prompt
            params["prompt"] = self.instantiate(prompt, context, allow_format_str_template)
        elif context:
            # Instantiate the messages
            params["messages"] = [
                {
                    **m,
                    "content": self.instantiate(m["content"], context, allow_format_str_template),
                }
                if m.get("content")
                else m
                for m in messages
            ]
        return params

    def _separate_create_config(self, config):
        """Separate the config into create_config and extra_kwargs."""
        create_config = {k: v for k, v in config.items() if k not in self.extra_kwargs}
        extra_kwargs = {k: v for k, v in config.items() if k in self.extra_kwargs}
        return create_config, extra_kwargs

    def _get_key(self, config):
        """Get a unique identifier of a configuration.

        Args:
            config (dict or list): A configuration.

        Returns:
            tuple: A unique identifier which can be used as a key for a dict.
        """
        NON_CACHE_KEY = ["api_key", "base_url", "api_type", "api_version"]
        copied = False
        for key in NON_CACHE_KEY:
            if key in config:
                config, copied = config.copy() if not copied else config, True
                config.pop(key)
        return json.dumps(config, sort_keys=True)

    async def create(self, **config):
        # merge the input config with the i-th config in the config list
        full_config = {**config}
        # separate the config into create_config and extra_kwargs
        create_config, extra_kwargs = self._separate_create_config(full_config)

        # construct the create params
        params = self._construct_create_params(create_config, extra_kwargs)
        # get the cache_seed, filter_func and context
        cache_seed = extra_kwargs.get("cache_seed", 66)
        filter_func = extra_kwargs.get("filter_func")
        context = extra_kwargs.get("context")
        llm_model = extra_kwargs.get("llm_model")
        if context:
            use_cache = context.get("use_cache", True)
            if not use_cache:
                cache_seed = None
        # Try to load the response from cache
        if cache_seed is not None:
            with diskcache.Cache(f"{self.cache_path_root}/{cache_seed}") as cache:
                # Try to get the response from cache
                key = self._get_key(params)
                response = cache.get(key, None)
                if response is not None:
                    # check the filter
                    pass_filter = filter_func is None or filter_func(context=context, response=response)
                    if pass_filter :
                        # Return the response if it passes the filter
                        # TODO: add response.cost
                        return response
        try:
             response = await self._completions_create(llm_model, params)
        except LLMChatError as e:
            logger.debug(f"{llm_model} generate failed!{str(e)}")
            raise e
        else:
            if cache_seed is not None:
                # Cache the response
                with diskcache.Cache(f"{self.cache_path_root}/{cache_seed}") as cache:
                    cache.set(key, response)

            # check the filter
            pass_filter = filter_func is None or filter_func(context=context, response=response)
            if pass_filter:
                # Return the response if it passes the filter
                return response

    def _get_span_metadata(self, payload: Dict) -> Dict:
        metadata = {k: v for k, v in payload.items()}
        del metadata["prompt"]
        metadata["messages"] = list(
            map(lambda m: m if isinstance(m, dict) else m.dict(), metadata["messages"])
        )
        return metadata

    def _llm_messages_convert(self, params):
        gpts_messages = params["messages"]
        ### TODO

        return gpts_messages

    async def _completions_create(self, llm_model, params):
        payload = {
            "model": llm_model,
            "prompt": params.get('prompt'),
            "messages": self._llm_messages_convert(params),
            "temperature": float(params.get('temperature')),
            "max_new_tokens": int(params.get('max_new_tokens')),
            # "stop": self.prompt_template.sep,
            "echo": self.llm_echo,
        }
        logger.info(f"Request: \n{payload}")
        ai_response_text = ""
        span = root_tracer.start_span(
            "BaseChat.nostream_call", metadata=self._get_span_metadata(payload)
        )
        payload["span_id"] = span.span_id
        payload["model_cache_enable"] = self.model_cache_enable
        try:
            model_output= await self._model_operator.call(
                call_data={"data": payload}
            )
            ai_response_text = (
                self.out_parser.parse_model_nostream_resp(
                    model_output, self.sep
                )
            )
            return ai_response_text
        except Exception as e:
            logger.error("model response parase faild！" + str(e))
            raise LLMChatError(original_exception=e) from e

    def _build_model_operator(self,
            is_stream: bool = False, dag_name: str = "llm_model_dag"
    ) -> BaseOperator:
        """Builds and returns a model processing workflow (DAG) operator.

        This function constructs a Directed Acyclic Graph (DAG) for processing data using a model.
        It includes caching and branching logic to either fetch results from a cache or process
        data using the model. It supports both streaming and non-streaming modes.

        .. code-block:: python
            input_node >> cache_check_branch_node
            cache_check_branch_node >> model_node >> save_cached_node >> join_node
            cache_check_branch_node >> cached_node >> join_node

        equivalent to::

                              -> model_node -> save_cached_node ->
                             /                                    \
            input_node -> cache_check_branch_node                   ---> join_node
                            \                                     /
                             -> cached_node ------------------- ->

        Args:
            is_stream (bool): Flag to determine if the operator should process data in streaming mode.
            dag_name (str): Name of the DAG.

        Returns:
            BaseOperator: The final operator in the constructed DAG, typically a join node.
        """
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.core.awel import JoinOperator
        from dbgpt.model.operator.model_operator import (
            ModelCacheBranchOperator,
            CachedModelStreamOperator,
            CachedModelOperator,
            ModelSaveCacheOperator,
            ModelStreamSaveCacheOperator,
        )
        from dbgpt.storage.cache import CacheManager

        # Fetch worker and cache managers from the system configuration
        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        cache_manager: CacheManager = CFG.SYSTEM_APP.get_component(
            ComponentType.MODEL_CACHE_MANAGER, CacheManager
        )
        # Define task names for the model and cache nodes
        model_task_name = "llm_model_node"
        cache_task_name = "llm_model_cache_node"

        with DAG(dag_name):
            # Create an input node
            input_node = InputOperator(SimpleCallDataInputSource())
            # Determine if the workflow should operate in streaming mode
            if is_stream:
                model_node = ModelStreamOperator(worker_manager, task_name=model_task_name)
                cached_node = CachedModelStreamOperator(
                    cache_manager, task_name=cache_task_name
                )
                save_cached_node = ModelStreamSaveCacheOperator(cache_manager)
            else:
                model_node = ModelOperator(worker_manager, task_name=model_task_name)
                cached_node = CachedModelOperator(cache_manager, task_name=cache_task_name)
                save_cached_node = ModelSaveCacheOperator(cache_manager)

            # Create a branch node to decide between fetching from cache or processing with the model
            cache_check_branch_node = ModelCacheBranchOperator(
                cache_manager,
                model_task_name="llm_model_node",
                cache_task_name="llm_model_cache_node",
            )
            # Create a join node to merge outputs from the model and cache nodes, just keep the first not empty output
            join_node = JoinOperator(
                combine_function=lambda model_out, cache_out: cache_out or model_out
            )

            # Define the workflow structure using the >> operator
            input_node >> cache_check_branch_node
            cache_check_branch_node >> model_node >> save_cached_node >> join_node
            cache_check_branch_node >> cached_node >> join_node

        return join_node

