"""AIWrapper for LLM."""

import json
import logging
from typing import Callable, Dict, Optional, Type, Union

from dbgpt.core import LLMClient, ModelOutput, ModelRequestContext
from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.tracer import root_tracer
from dbgpt.vis import Vis

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
        self,
        llm_client: LLMClient,
        output_parser: Optional[BaseOutputParser] = None,
        thinking_render: Optional[Type[Vis]] = None,
    ):
        """Create an AIWrapper instance."""
        self.llm_echo = False
        self.model_cache_enable = False
        self._llm_client = llm_client
        self._thinking_render = thinking_render
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
        # merge the input config with the i-th config in the config list
        full_config = {**config}
        # separate the config into create_config and extra_kwargs
        create_config, extra_kwargs = self._separate_create_config(full_config)
        params = self._construct_create_params(create_config, extra_kwargs)
        llm_model = extra_kwargs.get("llm_model")
        stream_out = extra_kwargs.get("stream_out", True)

        async for out in self._completions_create(llm_model, params, stream_out):
            yield out

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

    async def _completions_create(self, llm_model, params, stream_out: bool = True):
        payload = {
            "model": llm_model,
            "prompt": params.get("prompt"),
            "messages": self._llm_messages_convert(params),
            "temperature": float(params.get("temperature")),
            "max_new_tokens": int(params.get("max_new_tokens")),
            "echo": self.llm_echo,
            "trace_id": params.get("trace_id", None),
            "rpc_id": params.get("rpc_id", None),
        }
        # messages_prompt = '\n'.join(item['content'] for item in payload['messages'])
        # await self._llm_client.count_token(llm_model, messages_prompt)
        logger.info(f"Model:{llm_model},token count:none")
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
            from datetime import datetime

            start_time = datetime.now()
            if stream_out:
                async for output in self._llm_client.generate_stream(
                    model_request.copy()
                ):  # type: ignore
                    model_output: ModelOutput = output
                    # 恢复模型调用异常，触发后续的模型兜底策略
                    # 恢复模型调用异常，触发后续的模型兜底策略
                    if model_output.error_code != 0:
                        raise LLMChatError(
                            model_output.text,
                            original_exception=model_output.error_code,
                        )

                    parsed_output = model_output.gen_text_and_thinking()

                    think_blank = not parsed_output[0] or len(parsed_output[0]) <= 0
                    content_blank = not parsed_output[1] or len(parsed_output[1]) <= 0
                    if think_blank and content_blank:
                        continue
                    first_chunk = False

                    if first_chunk:
                        end_time = datetime.now()
                        logger.info(
                            f"LLM stream generate first token cost:{end_time - start_time} "
                            f"seconds. output is {parsed_output}"
                        )
                    yield parsed_output
            else:
                model_output = await self._llm_client.generate(model_request.copy())  # type: ignore
                # 恢复模型调用异常，触发后续的模型兜底策略
                if model_output.error_code != 0:
                    raise LLMChatError(
                        model_output.text, original_exception=model_output.error_code
                    )
                parsed_output = model_output.gen_text_and_thinking()
                # parsed_output = parsed_output.strip().replace("\\n", "\n")
                end_time = datetime.now()
                logger.info(
                    f"LLM no stream generate cost:{end_time - start_time} "
                    f"seconds. output is {parsed_output}"
                )
                yield parsed_output
        except LLMChatError:
            raise
        except Exception as e:
            logger.exception(f"Call LLMClient error, detail: {str(e)}")
            raise ValueError(f"LLM Request Exception!{str(e)}")
        finally:
            span.end()
