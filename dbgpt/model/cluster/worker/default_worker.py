import os
import logging

from typing import Dict, Iterator, List, Optional
import time
import traceback

from dbgpt.configs.model_config import get_device
from dbgpt.model.model_adapter import get_llm_model_adapter, LLMModelAdaper
from dbgpt.core import ModelOutput, ModelInferenceMetrics
from dbgpt.model.loader import ModelLoader, _get_model_real_path
from dbgpt.model.parameter import ModelParameters
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.util.model_utils import _clear_model_cache, _get_current_cuda_memory
from dbgpt.util.parameter_utils import EnvArgumentParser, _get_dict_from_obj
from dbgpt.util.tracer import root_tracer, SpanType, SpanTypeRunName
from dbgpt.util.system_utils import get_system_info

logger = logging.getLogger(__name__)

_torch_imported = False
try:
    import torch

    _torch_imported = True
except ImportError:
    pass


class DefaultModelWorker(ModelWorker):
    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None
        self._model_params = None
        self.llm_adapter: LLMModelAdaper = None
        self._support_async = False

    def load_worker(self, model_name: str, model_path: str, **kwargs) -> None:
        if model_path.endswith("/"):
            model_path = model_path[:-1]
        model_path = _get_model_real_path(model_name, model_path)
        self.model_name = model_name
        self.model_path = model_path

        model_type = kwargs.get("model_type")
        ### Temporary configuration, fastchat will be used by default in the future.
        use_fastchat = os.getenv("USE_FASTCHAT", "True").lower() == "true"

        self.llm_adapter = get_llm_model_adapter(
            self.model_name,
            self.model_path,
            use_fastchat=use_fastchat,
            model_type=model_type,
        )
        model_type = self.llm_adapter.model_type()
        self.param_cls = self.llm_adapter.model_param_class(model_type)
        self._support_async = self.llm_adapter.support_async()

        logger.info(
            f"model_name: {self.model_name}, model_path: {self.model_path}, model_param_class: {self.param_cls}"
        )

        self.ml: ModelLoader = ModelLoader(
            model_path=self.model_path, model_name=self.model_name
        )
        # Default model context len
        self.context_len = 2048

    def model_param_class(self) -> ModelParameters:
        return self.param_cls

    def support_async(self) -> bool:
        return self._support_async

    def parse_parameters(self, command_args: List[str] = None) -> ModelParameters:
        param_cls = self.model_param_class()
        model_args = EnvArgumentParser()
        env_prefix = EnvArgumentParser.get_env_prefix(self.model_name)
        model_type = self.llm_adapter.model_type()
        model_params: ModelParameters = model_args.parse_args_into_dataclass(
            param_cls,
            env_prefixes=[env_prefix, "LLM_"],
            command_args=command_args,
            model_name=self.model_name,
            model_path=self.model_path,
            model_type=model_type,
        )
        if not model_params.device:
            model_params.device = get_device()
            logger.info(
                f"[DefaultModelWorker] Parameters of device is None, use {model_params.device}"
            )
        return model_params

    def start(
        self, model_params: ModelParameters = None, command_args: List[str] = None
    ) -> None:
        if not model_params:
            model_params = self.parse_parameters(command_args)
        self._model_params = model_params
        logger.info(f"Begin load model, model params: {model_params}")
        metadata = {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "model_type": self.llm_adapter.model_type(),
            "llm_adapter": str(self.llm_adapter),
            "run_service": SpanTypeRunName.MODEL_WORKER,
            "params": _get_dict_from_obj(model_params),
            "sys_infos": _get_dict_from_obj(get_system_info()),
        }
        with root_tracer.start_span(
            "DefaultModelWorker.start", span_type=SpanType.RUN, metadata=metadata
        ):
            self.model, self.tokenizer = self.ml.loader_with_params(
                model_params, self.llm_adapter
            )
            model_max_length = _parse_model_max_length(self.model, self.tokenizer)
            if model_max_length:
                logger.info(
                    f"Parse model max length {model_max_length} from model {self.model_name}."
                )
                self.context_len = model_max_length

    def stop(self) -> None:
        if not self.model:
            logger.warn("Model has been stopped!!")
            return
        del self.model
        del self.tokenizer
        self.model = None
        self.tokenizer = None
        _clear_model_cache(self._model_params.device)

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
            print(
                f"\n\nfull stream output:\n{previous_response}\n\nmodel generate_stream params:\n{params}"
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
        for out in self.generate_stream(params):
            output = out
        return output

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
            print(
                f"\n\nfull stream output:\n{previous_response}\n\nmodel generate_stream params:\n{params}"
            )
            model_span.end(metadata={"output": previous_response})
            span.end()
        except Exception as e:
            output = self._handle_exception(e)
            yield output
            span.end(metadata={"error": output.to_dict()})

    async def async_generate(self, params: Dict) -> ModelOutput:
        output = None
        async for out in self.async_generate_stream(params):
            output = out
        return output

    def _prepare_generate_stream(self, params: Dict, span_operation_name: str):
        params, model_context = self.llm_adapter.model_adaptation(
            params,
            self.model_name,
            self.model_path,
            self.tokenizer,
            prompt_template=self.ml.prompt_template,
        )
        stream_type = ""
        if self.support_async():
            generate_stream_func = self.llm_adapter.get_async_generate_stream_function(
                self.model, self.model_path
            )
            stream_type = "async "
            logger.info(
                "current generate stream function is asynchronous stream function"
            )
        else:
            generate_stream_func = self.llm_adapter.get_generate_stream_function(
                self.model, self.model_path
            )
        str_prompt = params.get("prompt")
        print(
            f"llm_adapter: {str(self.llm_adapter)}\n\nmodel prompt: \n\n{str_prompt}\n\n{stream_type}stream output:\n"
        )

        generate_stream_func_str_name = "{}.{}".format(
            generate_stream_func.__module__, generate_stream_func.__name__
        )

        span_params = {k: v for k, v in params.items()}
        if "messages" in span_params:
            span_params["messages"] = list(
                map(lambda m: m.dict(), span_params["messages"])
            )

        model_span = root_tracer.start_span(
            span_operation_name,
            metadata={
                "prompt": str_prompt,
                "params": span_params,
                "is_async_func": self.support_async(),
                "llm_adapter": str(self.llm_adapter),
                "generate_stream_func": generate_stream_func_str_name,
                "model_context": model_context,
            },
        )

        return params, model_context, generate_stream_func, model_span

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
            output = output["text"]
            if finish_reason is not None:
                logger.info(f"finish_reason: {finish_reason}")
        incremental_output = output[len(previous_response) :]
        print(incremental_output, end="", flush=True)

        metrics = _new_metrics_from_model_output(last_metrics, is_first_generate, usage)
        model_output = ModelOutput(
            text=output,
            error_code=0,
            model_context=model_context,
            finish_reason=finish_reason,
            usage=usage,
            metrics=metrics,
        )
        return model_output, incremental_output, output, metrics

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
