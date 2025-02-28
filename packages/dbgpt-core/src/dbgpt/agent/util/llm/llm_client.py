"""AIWrapper for LLM."""

import json
import logging
import traceback
from typing import Any, Callable, Dict, Optional, Union

from dbgpt.core import LLMClient, ModelOutput, ModelRequestContext
from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.tracer import root_tracer

from ..llm.llm import _build_model_request

logger = logging.getLogger(__name__)


class AIWrapper:
    """AIWrapper for LLM."""

    cache_path_root: str = ".cache"
    extra_kwargs = {
        "cache_seed",
        "filter_func",
        "allow_format_str_template",
        "context",
        "llm_model",
        "memory",
        "conv_id",
        "sender",
        "stream_out",
    }

    def __init__(
        self, llm_client: LLMClient, output_parser: Optional[BaseOutputParser] = None
    ):
        """Create an AIWrapper instance."""
        self.llm_echo = False
        self.model_cache_enable = False
        self._llm_client = llm_client
        self._output_parser = output_parser or BaseOutputParser(is_stream_out=False)

    @classmethod
    def instantiate(
        cls,
        template: Optional[Union[str, Callable]] = None,
        context: Optional[Dict] = None,
        allow_format_str_template: Optional[bool] = False,
    ):
        """Instantiate the template with the context."""
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
        if prompt is None and messages is None:
            raise ValueError(
                "Either prompt or messages should be in create config but not both."
            )

        context = extra_kwargs.get("context")
        if context is None:
            # No need to instantiate if no context is provided.
            return create_config
        # Instantiate the prompt or messages
        allow_format_str_template = extra_kwargs.get("allow_format_str_template", False)
        # Make a copy of the config
        params = create_config.copy()
        params["context"] = context

        if prompt is not None:
            # Instantiate the prompt
            params["prompt"] = self.instantiate(
                prompt, context, allow_format_str_template
            )
        elif context and messages and isinstance(messages, list):
            # Instantiate the messages
            params["messages"] = [
                (
                    {
                        **m,
                        "content": self.instantiate(
                            m["content"], context, allow_format_str_template
                        ),
                    }
                    if m.get("content")
                    else m
                )
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
        non_cache_key = ["api_key", "base_url", "api_type", "api_version"]
        copied = False
        for key in non_cache_key:
            if key in config:
                config, copied = config.copy() if not copied else config, True
                config.pop(key)
        return json.dumps(config, sort_keys=True, ensure_ascii=False)

    async def create(self, verbose: bool = False, **config):
        """Create llm client request."""
        # merge the input config with the i-th config in the config list
        full_config = {**config}
        # separate the config into create_config and extra_kwargs
        create_config, extra_kwargs = self._separate_create_config(full_config)

        # construct the create params
        params = self._construct_create_params(create_config, extra_kwargs)
        # get the cache_seed, filter_func and context
        filter_func = extra_kwargs.get("filter_func")
        context = extra_kwargs.get("context")
        llm_model = extra_kwargs.get("llm_model")
        memory = extra_kwargs.get("memory", None)
        conv_id = extra_kwargs.get("conv_id", None)
        sender = extra_kwargs.get("sender", None)
        stream_out = extra_kwargs.get("stream_out", True)

        try:
            response = await self._completions_create(
                llm_model, params, conv_id, sender, memory, stream_out, verbose
            )
        except LLMChatError as e:
            logger.debug(f"{llm_model} generate failed!{str(e)}")
            raise e
        else:
            pass_filter = filter_func is None or filter_func(
                context=context, response=response
            )
            if pass_filter:
                # Return the response if it passes the filter
                return response
            else:
                return None

    def _get_span_metadata(self, payload: Dict) -> Dict:
        metadata = {k: v for k, v in payload.items()}

        metadata["messages"] = list(
            map(lambda m: m if isinstance(m, dict) else m.dict(), metadata["messages"])
        )
        return metadata

    def _llm_messages_convert(self, params):
        gpts_messages = params["messages"]
        # TODO

        return gpts_messages

    async def _completions_create(
        self,
        llm_model,
        params,
        conv_id: Optional[str] = None,
        sender: Optional[str] = None,
        memory: Optional[Any] = None,
        stream_out: bool = True,
        verbose: bool = False,
    ):
        payload = {
            "model": llm_model,
            "prompt": params.get("prompt"),
            "messages": self._llm_messages_convert(params),
            "temperature": float(params.get("temperature")),
            "max_new_tokens": int(params.get("max_new_tokens")),
            "echo": self.llm_echo,
        }
        logger.info(f"Request: \n{payload}")
        span = root_tracer.start_span(
            "Agent.llm_client.no_streaming_call",
            metadata=self._get_span_metadata(payload),
        )
        payload["span_id"] = span.span_id
        payload["model_cache_enable"] = self.model_cache_enable
        if params.get("context") is not None:
            payload["context"] = ModelRequestContext(extra=params["context"])
        try:
            model_request = _build_model_request(payload)
            str_prompt = model_request.messages_to_string()
            model_output: Optional[ModelOutput] = None
            async for output in self._llm_client.generate_stream(model_request.copy()):  # type: ignore # noqa
                model_output = output
                if memory and stream_out:
                    from ... import GptsMemory  # noqa: F401

                    temp_message = {
                        "sender": sender,
                        "receiver": "?",
                        "model": llm_model,
                        "markdown": model_output.gen_text_with_thinking(),
                    }
                    await memory.push_message(
                        conv_id,
                        temp_message,
                    )
            if not model_output:
                raise ValueError("LLM generate stream is null!")
            parsed_output = model_output.gen_text_with_thinking()
            parsed_output = parsed_output.strip().replace("\\n", "\n")

            if verbose:
                print("\n", "-" * 80, flush=True, sep="")
                print(f"String Prompt[verbose]: \n{str_prompt}")
                print(f"LLM Output[verbose]: \n{parsed_output}")
                print("-" * 80, "\n", flush=True, sep="")
            return parsed_output
        except Exception as e:
            logger.error(
                f"Call LLMClient error, {str(e)}, detail: {traceback.format_exc()}"
            )
            raise LLMChatError(original_exception=e) from e
        finally:
            span.end()
