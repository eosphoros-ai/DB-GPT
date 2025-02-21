from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Type

from dbgpt.core import ModelMetadata, ModelOutput
from dbgpt.core.interface.parameter import BaseDeployModelParameters
from dbgpt.model.parameter import WorkerType
from dbgpt.util.parameter_utils import ParameterDescription, _get_parameter_descriptions


class ModelWorker(ABC):
    """
    Abstract representation of a Model Worker responsible for model interaction,
    startup, and shutdown. Supports 'llm' and 'text2vec' models.
    """

    def worker_type(self) -> WorkerType:
        """Return the type of worker as LLM."""
        return WorkerType.LLM

    def model_param_class(self) -> Type[BaseDeployModelParameters]:
        """Return the class representing model parameters."""
        raise BaseDeployModelParameters

    def support_async(self) -> bool:
        """Whether support async, if True, invoke async_generate_stream, async_generate
        and async_embeddings instead of generate_stream, generate and embeddings"""
        return False

    # @abstractmethod
    # def parse_parameters(self, command_args: List[str] = None) -> ModelParameters:
    #     """Parse the parameters using the provided command arguments.
    #
    #     Args:
    #         command_args (List[str]): The command-line arguments. Default is
    #             sys.argv[1:].
    #     """

    @abstractmethod
    def load_worker(
        self, model_name: str, deploy_model_params: BaseDeployModelParameters, **kwargs
    ) -> None:
        """Load the model worker.

        Args:
            model_name (str): The model name.
            deploy_model_params (BaseDeployModelParameters): The deploy model
                parameters.
            **kwargs: Additional keyword arguments.
        """

    @abstractmethod
    def start(self, command_args: List[str] = None) -> None:
        """Start the model worker"""

    @abstractmethod
    def stop(self) -> None:
        """Stop the model worker and clean up all the resources used."""

    def restart(self, command_args: List[str] = None) -> None:
        """Restart the model worker."""
        self.stop()
        self.start(command_args)

    def parameter_descriptions(self) -> List[ParameterDescription]:
        """Fetch the parameter configuration information for the current model."""
        param_cls = self.model_param_class()
        return _get_parameter_descriptions(param_cls)

    @abstractmethod
    def generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        """Generate a stream based on provided parameters.

        Args:
            params (Dict): Parameters matching the PromptRequest data class format.
                Example:
                {
                    # List of ModelMessage objects
                    "messages": [{"role": "user", "content": "Hello world"}],
                    "model": "vicuna-13b-v1.5",
                    "prompt": "Hello world",
                    "temperature": 0.7,  # Optional; float value between 0 and 1
                    # Optional; max number of new tokens for the output
                    "max_new_tokens": 2048,
                    "stop": "#",  # Optional; stopping condition for the output
                    "echo": True  # Optional; whether to echo the input in the output
                }

        Returns:
            Iterator[ModelOutput]: Stream of model outputs.
        """

    async def async_generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        """Asynchronously generate a stream based on provided parameters."""
        raise NotImplementedError

    @abstractmethod
    def generate(self, params: Dict) -> ModelOutput:
        """Generate output (non-stream) based on provided parameters."""

    async def async_generate(self, params: Dict) -> ModelOutput:
        """Asynchronously generate output (non-stream) based on provided parameters."""
        raise NotImplementedError

    @abstractmethod
    def count_token(self, prompt: str) -> int:
        """Count token of prompt
        Args:
            prompt (str): prompt

        Returns:
            int: token count
        """

    async def async_count_token(self, prompt: str) -> int:
        """Asynchronously count token of prompt
        Args:
            prompt (str): prompt

        Returns:
            int: token count
        """
        raise NotImplementedError

    @abstractmethod
    def get_model_metadata(self, params: Dict) -> ModelMetadata:
        """Get model metadata

        Args:
            params (Dict): parameters, eg. {"model": "vicuna-13b-v1.5"}
        """

    async def async_get_model_metadata(self, params: Dict) -> ModelMetadata:
        """Asynchronously get model metadata

        Args:
            params (Dict): parameters, eg. {"model": "vicuna-13b-v1.5"}
        """
        raise NotImplementedError

    @abstractmethod
    def embeddings(self, params: Dict) -> List[List[float]]:
        """
        Return embeddings for the given input parameters.

        Args:
            params (Dict): Parameters matching the EmbeddingsRequest data class format.
             Example:
                {
                    "model": "text2vec-large-chinese",
                    "input": ["Hello world", "DB-GPT is amazing"]
                }

        Returns:
            List[List[float]]: List of embeddings corresponding to each input string.
        """

    async def async_embeddings(self, params: Dict) -> List[List[float]]:
        """Return embeddings asynchronously for the given input parameters."""
        raise NotImplementedError
