import logging
import os
import time
import traceback
from typing import Dict, Iterator, List, Optional, Type

from dbgpt.configs.model_config import get_device
from dbgpt.core import (
    ModelExtraMedata,
    ModelInferenceMetrics,
    ModelMetadata,
    ModelOutput,
)
from dbgpt.core.interface.parameter import (
    BaseDeployModelParameters,
    LLMDeployModelParameters,
)
from dbgpt.model.adapter.base import LLMModelAdapter
from dbgpt.model.adapter.loader import ModelLoader
from dbgpt.model.adapter.model_adapter import get_llm_model_adapter
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.util.model_utils import _clear_model_cache, _get_current_cuda_memory
from dbgpt.util.parameter_utils import _get_dict_from_obj
from dbgpt.util.system_utils import get_system_info
from dbgpt.util.tracer import SpanType, SpanTypeRunName, root_tracer

logger = logging.getLogger(__name__)

_torch_imported = False
torch = None


class DefaultModelWorker(ModelWorker):
    def __init__(self) -> None:
        self.model_name: Optional[str] = None
        self.model_path: Optional[str] = None
        self.model = None
        self.tokenizer = None
        self._model_params: Optional[LLMDeployModelParameters] = None
        self._param_cls: Optional[Type[LLMDeployModelParameters]] = None
        self.llm_adapter: LLMModelAdapter = None
        self._support_async = False
        self._support_generate_func = False
        self.context_len = 4096
        self._device = get_device()

    def load_worker(
        self, model_name: str, deploy_model_params: BaseDeployModelParameters, **kwargs
    ) -> None:
        if not isinstance(deploy_model_params, LLMDeployModelParameters):
            raise ValueError(
                f"deploy_model_params should be LLMDeployModelParameters, but got "
                f"{type(deploy_model_params)}"
            )
        self._model_params = deploy_model_params
        self._param_cls = deploy_model_params.__class__
        if deploy_model_params.real_device:
            # Use the configured device
            self._device = deploy_model_params.real_device

        model_path = deploy_model_params.real_model_path

        # model_path = _get_model_real_path(model_name, model_path)
        self.model_name = model_name
        self.model_path = model_path

        # Temporary configuration, fastchat will be used by default in the future.
        use_fastchat = os.getenv("USE_FASTCHAT", "False").lower() == "true"

        self.llm_adapter = get_llm_model_adapter(
            self.model_name,
            model_path,
            use_fastchat=use_fastchat,
            model_type=deploy_model_params.provider,
        )
        # self._param_cls = self.llm_adapter.model_param_class(model_type)
        self._support_async = self.llm_adapter.support_async()
        self._support_generate_func = self.llm_adapter.support_generate_function()

        logger.info(
            f"model_name: {self.model_name}, model_path: {model_path}, "
            f"model_param_class: {self._param_cls}"
        )

        self.ml: ModelLoader = ModelLoader(
            prompt_template=self._model_params.prompt_template
        )
        # Default model context len
        self.context_len = 4096

    def model_param_class(self) -> Type[LLMDeployModelParameters]:
        return self._param_cls

    def support_async(self) -> bool:
        return self._support_async

    # def parse_parameters(self, command_args: List[str] = None) -> ModelParameters:
    #     raise NotImplementedError

    def start(self, command_args: List[str] = None) -> None:
        # Lazy load torch
        _try_import_torch()
        logger.info(f"Begin load model, model params: {self._model_params}")
        metadata = {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "model_type": self.llm_adapter.model_type(),
            "llm_adapter": str(self.llm_adapter),
            "run_service": SpanTypeRunName.MODEL_WORKER,
            "params": _get_dict_from_obj(self._model_params),
            "sys_infos": _get_dict_from_obj(get_system_info()),
        }
        with root_tracer.start_span(
            "DefaultModelWorker.start", span_type=SpanType.RUN, metadata=metadata
        ):
            try:
                self.model, self.tokenizer = self.ml.loader_with_params(
                    self._model_params, self.llm_adapter
                )
            except Exception:
                # try to clear cache
                _clear_model_cache(self._device)
                raise
            parsed_model_max_length = self.llm_adapter.parse_max_length(
                self.model, self.tokenizer
            )
            if (
                self._model_params.context_length
                and self._model_params.context_length > 0
            ):
                # Use context length from model params
                self.context_len = self._model_params.context_length
            elif parsed_model_max_length:
                logger.info(
                    f"Parse model max length {parsed_model_max_length} from model "
                    f"{self.model_name}."
                )
                self.context_len = parsed_model_max_length
            elif hasattr(self._model_params, "max_context_size"):
                self.context_len = self._model_params.max_context_size
            elif hasattr(self._model_params, "model_max_length"):
                self.context_len = self._model_params.model_max_length

    def stop(self) -> None:
        if not self.model:
            logger.warning("Model has been stopped!!")
            return
        del self.model
        del self.tokenizer
        self.model = None
        self.tokenizer = None
        _clear_model_cache(self._device)

    def generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        span = root_tracer.start_span(
            "DefaultModelWorker.generate_stream", params.get("span_id")
        )
        try:
            (
                params,
                model_context,
                generate_stream_func,
                model_span,
            ) = self._prepare_generate_stream(
                params,
                span_operation_name="DefaultModelWorker_call.generate_stream_func",
            )

            previous_response = ""
            last_metrics = ModelInferenceMetrics.create_metrics()
            is_first_generate = True

            context_len = params.get("context_len") or self.context_len
            for output in generate_stream_func(
                self.model, self.tokenizer, params, get_device(), context_len
            ):
                (
                    model_output,
                    incremental_output,
                    output_str,
                    current_metrics,
                ) = self._handle_output(
                    output,
                    previous_response,
                    model_context,
                    last_metrics,
                    is_first_generate,
                )
                if is_first_generate:
                    is_first_generate = False
                previous_response = output_str
                last_metrics = current_metrics
                yield model_output
            logger.info(
                f"\n\nfull stream output:\n{previous_response}\n\nmodel "
                f"generate_stream params:\n{params}"
            )
            model_span.end(metadata={"output": previous_response})
            span.end()
        except Exception as e:
            output = self._handle_exception(e)
            yield output
            span.end(metadata={"error": output.to_dict()})

    def generate(self, params: Dict) -> ModelOutput:
        """Generate non stream result"""
        output = None
        if self._support_generate_func:
            (
                params,
                model_context,
                generate_stream_func,
                model_span,
            ) = self._prepare_generate_stream(
                params,
                span_operation_name="DefaultModelWorker_call.generate_func",
                is_stream=False,
            )
            previous_response = ""
            last_metrics = ModelInferenceMetrics.create_metrics()
            is_first_generate = True
            output = generate_stream_func(
                self.model, self.tokenizer, params, get_device(), self.context_len
            )
            (
                model_output,
                incremental_output,
                output_str,
                current_metrics,
            ) = self._handle_output(
                output,
                previous_response,
                model_context,
                last_metrics,
                is_first_generate,
            )
            return model_output
        else:
            for out in self.generate_stream(params):
                output = out
            return output

    def count_token(self, prompt: str) -> int:
        return _try_to_count_token(prompt, self.tokenizer, self.model)

    async def async_count_token(self, prompt: str) -> int:
        # TODO if we deploy the model by vllm, it can't work, we should run
        #  transformer _try_to_count_token to async
        from dbgpt.model.proxy.llms.proxy_model import ProxyModel

        if isinstance(self.model, ProxyModel) and self.model.proxy_llm_client:
            return await self.model.proxy_llm_client.count_token(
                self.model.proxy_llm_client.default_model, prompt
            )
        raise NotImplementedError

    def get_model_metadata(self, params: Dict) -> ModelMetadata:
        ext_metadata = ModelExtraMedata(
            prompt_roles=self.llm_adapter.get_prompt_roles(),
            prompt_sep=self.llm_adapter.get_default_message_separator(),
        )
        return ModelMetadata(
            model=self.model_name,
            context_length=self.context_len,
            ext_metadata=ext_metadata,
        )

    async def async_get_model_metadata(self, params: Dict) -> ModelMetadata:
        return self.get_model_metadata(params)

    def embeddings(self, params: Dict) -> List[List[float]]:
        raise NotImplementedError

    async def async_generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        span = root_tracer.start_span(
            "DefaultModelWorker.async_generate_stream", params.get("span_id")
        )
        try:
            (
                params,
                model_context,
                generate_stream_func,
                model_span,
            ) = self._prepare_generate_stream(
                params,
                span_operation_name="DefaultModelWorker_call.generate_stream_func",
            )

            previous_response = ""
            context_len = params.get("context_len") or self.context_len

            last_metrics = ModelInferenceMetrics.create_metrics()
            is_first_generate = True
            async for output in generate_stream_func(
                self.model, self.tokenizer, params, get_device(), context_len
            ):
                (
                    model_output,
                    incremental_output,
                    output_str,
                    current_metrics,
                ) = self._handle_output(
                    output,
                    previous_response,
                    model_context,
                    last_metrics,
                    is_first_generate,
                )
                if is_first_generate:
                    is_first_generate = False

                previous_response = output_str
                last_metrics = current_metrics
                yield model_output
            logger.info(
                f"\n\nfull stream output:\n{previous_response}\n\nmodel "
                f"generate_stream params:\n{params}"
            )
            model_span.end(metadata={"output": previous_response})
            span.end()
        except Exception as e:
            output = self._handle_exception(e)
            yield output
            span.end(metadata={"error": output.to_dict()})

    async def async_generate(self, params: Dict) -> ModelOutput:
        if self._support_generate_func:
            (
                params,
                model_context,
                generate_stream_func,
                model_span,
            ) = self._prepare_generate_stream(
                params,
                span_operation_name="DefaultModelWorker_call.generate_func",
                is_stream=False,
            )
            previous_response = ""
            last_metrics = ModelInferenceMetrics.create_metrics()
            is_first_generate = True
            output = await generate_stream_func(
                self.model, self.tokenizer, params, get_device(), self.context_len
            )
            (
                model_output,
                incremental_output,
                output_str,
                current_metrics,
            ) = self._handle_output(
                output,
                previous_response,
                model_context,
                last_metrics,
                is_first_generate,
            )
            return model_output
        else:
            output = None
            async for out in self.async_generate_stream(params):
                output = out
            return output

    def _prepare_generate_stream(
        self, params: Dict, span_operation_name: str, is_stream=True
    ):
        params, model_context = self.llm_adapter.model_adaptation(
            params,
            self.model_name,
            self.model_path,
            self.tokenizer,
            prompt_template=self.ml.prompt_template,
        )
        if self.support_async():
            if not is_stream and self.llm_adapter.support_generate_function():
                func = self.llm_adapter.get_generate_function(
                    self.model, self._model_params
                )
                func_type = "async generate"
                logger.info(
                    "current generate function is asynchronous generate function"
                )
            else:
                func = self.llm_adapter.get_async_generate_stream_function(
                    self.model, self._model_params
                )
                func_type = "async generate stream"
                logger.info(
                    "current generate stream function is asynchronous generate stream"
                    " function"
                )
        else:
            if not is_stream and self.llm_adapter.support_generate_function():
                func = self.llm_adapter.get_generate_function(
                    self.model, self._model_params
                )
                func_type = "generate"
                logger.info(
                    "current generate function is synchronous generate function"
                )
            else:
                func = self.llm_adapter.get_generate_stream_function(
                    self.model, self._model_params
                )
                func_type = "generate stream"
                logger.info(
                    "current generate stream function is synchronous generate stream "
                    "function"
                )
        str_prompt = params.get("prompt")
        if not str_prompt:
            str_prompt = params.get("string_prompt")
        logger.info(
            f"llm_adapter: {str(self.llm_adapter)}\n\nmodel prompt: \n\n"
            f"{str_prompt}\n\n{func_type} output:\n"
        )

        generate_func_str_name = "{}.{}".format(func.__module__, func.__name__)

        span_params = {k: v for k, v in params.items()}
        if "messages" in span_params:
            span_params["messages"] = list(
                map(lambda m: m.dict(), span_params["messages"])
            )
        if self.llm_adapter.is_reasoning_model(
            self._model_params, self.model_name.lower()
        ):
            params["is_reasoning_model"] = True

        metadata = {
            "is_async_func": self.support_async(),
            "llm_adapter": str(self.llm_adapter),
            "generate_func": generate_func_str_name,
        }
        metadata.update(span_params)
        metadata.update(model_context)
        metadata["prompt"] = str_prompt

        model_span = root_tracer.start_span(span_operation_name, metadata=metadata)

        return params, model_context, func, model_span

    def _handle_output(
        self,
        output,
        previous_response,
        model_context,
        last_metrics: ModelInferenceMetrics,
        is_first_generate: bool,
    ):
        finish_reason = None
        usage = None
        if isinstance(output, dict):
            finish_reason = output.get("finish_reason")
            usage = output.get("usage")
            if finish_reason is not None:
                logger.info(f"finish_reason: {finish_reason}")
            error_code = output.get("error_code", 0)
            model_output = ModelOutput.build(
                output["text"],
                thinking=None,
                error_code=error_code,
                usage=usage,
                finish_reason=finish_reason,
            )
        elif isinstance(output, ModelOutput):
            finish_reason = output.finish_reason
            usage = output.usage
            model_output = output
        elif isinstance(output, str):
            # Output is string
            model_output = ModelOutput.build(output)
        else:
            raise ValueError(f"Invalid output type: {type(output)}")
        current_output = ""
        if model_output.has_thinking:
            current_output = model_output.thinking_text or ""
        if model_output.has_text:
            current_output += model_output.text
        incremental_output = current_output[len(previous_response) :]
        print(incremental_output, end="", flush=True)

        metrics = _new_metrics_from_model_output(last_metrics, is_first_generate, usage)
        model_output.metrics = metrics
        model_output.model_context = model_context
        return model_output, incremental_output, current_output, metrics

    def _handle_exception(self, e):
        # Check if the exception is a torch.cuda.CudaError and if torch was imported.
        if _torch_imported and isinstance(e, torch.cuda.CudaError):
            model_output = ModelOutput(
                text="**GPU OutOfMemory, Please Refresh.**", error_code=1
            )
        else:
            msg = traceback.format_exc()
            logger.error(f"Model inference error, detail: {msg}")
            model_output = ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
        return model_output


def _parse_model_max_length(model, tokenizer) -> Optional[int]:
    if not (tokenizer or model):
        return None
    try:
        if tokenizer and hasattr(tokenizer, "model_max_length"):
            return tokenizer.model_max_length
        if model and hasattr(model, "config"):
            model_config = model.config
            if hasattr(model_config, "max_sequence_length"):
                return model_config.max_sequence_length
            if hasattr(model_config, "max_position_embeddings"):
                return model_config.max_position_embeddings
    except Exception:
        return None


def _new_metrics_from_model_output(
    last_metric: ModelInferenceMetrics,
    is_first_generate: bool,
    usage: Optional[Dict] = None,
) -> ModelInferenceMetrics:
    metrics = ModelInferenceMetrics.create_metrics(last_metric)
    metrics.collect_index = last_metric.collect_index + 1
    if is_first_generate:
        logger.info(f"is_first_generate, usage: {usage}")
        metrics.first_completion_time_ms = time.time_ns() // 1_000_000

    if not usage or not isinstance(usage, dict):
        return metrics
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")

    if prompt_tokens is None:
        prompt_tokens = metrics.prompt_tokens
    if completion_tokens is None:
        completion_tokens = metrics.completion_tokens
    if total_tokens is None:
        total_tokens = metrics.total_tokens

    if is_first_generate and (completion_tokens is not None):
        # completion_tokens == 0 is prefill
        metrics.first_completion_tokens = completion_tokens
        if completion_tokens == 1:
            metrics.first_token_time_ms = metrics.first_completion_time_ms
    if (
        not is_first_generate
        and metrics.first_token_time_ms is None
        and completion_tokens == 1
    ):
        # Case: first generate has 0 token, and second generate has 1 token
        metrics.first_token_time_ms = time.time_ns() // 1_000_000

    if prompt_tokens:
        metrics.prompt_tokens = prompt_tokens
    if completion_tokens:
        metrics.completion_tokens = completion_tokens
    if total_tokens:
        metrics.total_tokens = total_tokens
    elif prompt_tokens and completion_tokens:
        total_tokens = prompt_tokens + completion_tokens
        metrics.total_tokens = total_tokens

    if total_tokens:
        # time cost(seconds)
        duration = (metrics.current_time_ms - metrics.start_time_ms) / 1000.0
        metrics.speed_per_second = total_tokens / duration

    current_gpu_infos = _get_current_cuda_memory()
    metrics.current_gpu_infos = current_gpu_infos
    if not metrics.avg_gpu_infos:
        metrics.avg_gpu_infos = current_gpu_infos
    elif current_gpu_infos:
        for i, last_avg in enumerate(metrics.avg_gpu_infos):
            allocated_memory_gb = (
                last_avg.allocated_memory_gb * (metrics.collect_index - 1)
                + current_gpu_infos[i].allocated_memory_gb
            )
            metrics.avg_gpu_infos[i].allocated_memory_gb = (
                allocated_memory_gb / metrics.collect_index
            )
            metrics.avg_gpu_infos[i].total_memory_gb = current_gpu_infos[
                i
            ].total_memory_gb
            metrics.avg_gpu_infos[i].cached_memory_gb = current_gpu_infos[
                i
            ].cached_memory_gb
            metrics.avg_gpu_infos[i].available_memory_gb = current_gpu_infos[
                i
            ].available_memory_gb

    return metrics


def _try_to_count_token(prompt: str, tokenizer, model) -> int:
    """Try to count token of prompt

    Args:
        prompt (str): prompt
        tokenizer ([type]): tokenizer
        model ([type]): model

    Returns:
        int: token count, if error return -1

    TODO: More implementation
    """
    try:
        from dbgpt.model.proxy.llms.proxy_model import ProxyModel

        if isinstance(model, ProxyModel):
            return model.count_token(prompt)
        # Only support huggingface model now
        return len(tokenizer(prompt).input_ids[0])
    except Exception as e:
        logger.warning(f"Count token error, detail: {e}, return -1")
        return -1


def _try_import_torch():
    global torch
    global _torch_imported
    try:
        import torch

        _torch_imported = True
    except ImportError:
        pass
