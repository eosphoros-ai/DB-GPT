import os
import logging
from typing import Dict, Iterator, List

from pilot.configs.model_config import get_device
from pilot.model.model_adapter import get_llm_model_adapter, LLMModelAdaper
from pilot.model.base import ModelOutput
from pilot.model.loader import ModelLoader, _get_model_real_path
from pilot.model.parameter import ModelParameters
from pilot.model.cluster.worker_base import ModelWorker
from pilot.utils.model_utils import _clear_model_cache
from pilot.utils.parameter_utils import EnvArgumentParser, _get_dict_from_obj
from pilot.utils.tracer import root_tracer, SpanType, SpanTypeRunName
from pilot.utils.system_utils import get_system_info

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
        # TODO read context len from model config
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

            for output in generate_stream_func(
                self.model, self.tokenizer, params, get_device(), self.context_len
            ):
                model_output, incremental_output, output_str = self._handle_output(
                    output, previous_response, model_context
                )
                previous_response = output_str
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

            async for output in generate_stream_func(
                self.model, self.tokenizer, params, get_device(), self.context_len
            ):
                model_output, incremental_output, output_str = self._handle_output(
                    output, previous_response, model_context
                )
                previous_response = output_str
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
        print(f"model prompt: \n\n{str_prompt}\n\n{stream_type}stream output:\n")

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

    def _handle_output(self, output, previous_response, model_context):
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
        model_output = ModelOutput(
            text=output,
            error_code=0,
            model_context=model_context,
            finish_reason=finish_reason,
            usage=usage,
        )
        return model_output, incremental_output, output

    def _handle_exception(self, e):
        # Check if the exception is a torch.cuda.CudaError and if torch was imported.
        if _torch_imported and isinstance(e, torch.cuda.CudaError):
            model_output = ModelOutput(
                text="**GPU OutOfMemory, Please Refresh.**", error_code=0
            )
        else:
            model_output = ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=0,
            )
        return model_output
