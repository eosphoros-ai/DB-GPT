"""LLM Utility For Agent Memory."""

import re
from typing import List, Optional, Union

from dbgpt._private.pydantic import BaseModel
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    LLMClient,
    ModelMessage,
    ModelRequest,
)

from .base import ImportanceScorer, InsightExtractor, InsightMemoryFragment, T


class BaseLLMCaller(BaseModel):
    """Base class for LLM caller."""

    prompt: str = ""
    model: Optional[str] = None

    async def call_llm(
        self,
        prompt: Union[ChatPromptTemplate, str],
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ) -> str:
        """Call LLM client to generate response.

        Args:
            llm_client(LLMClient): LLM client
            prompt(ChatPromptTemplate): prompt
            **kwargs: other keyword arguments

        Returns:
            str: response
        """
        if not llm_client:
            raise ValueError("LLM client is required.")
        if isinstance(prompt, str):
            prompt = ChatPromptTemplate(
                messages=[HumanPromptTemplate.from_template(prompt)]
            )
        model = self.model
        if not model:
            model = await self.get_model(llm_client)
        prompt_kwargs = {}
        prompt_kwargs.update(kwargs)
        pass_kwargs = {
            k: v for k, v in prompt_kwargs.items() if k in prompt.input_variables
        }
        messages = prompt.format_messages(**pass_kwargs)
        model_messages = ModelMessage.from_base_messages(messages)
        model_request = ModelRequest.build_request(model, messages=model_messages)
        model_output = await llm_client.generate(model_request)
        if not model_output.success:
            raise ValueError("Call LLM failed.")
        return model_output.text

    async def get_model(self, llm_client: LLMClient) -> str:
        """Get the model.

        Args:
            llm_client(LLMClient): LLM client

        Returns:
            str: model
        """
        models = await llm_client.models()
        if not models:
            raise ValueError("No models available.")
        self.model = models[0].model
        return self.model

    @staticmethod
    def _parse_list(text: str) -> List[str]:
        """Parse a newline-separated string into a list of strings.

        1. First, split by newline
        2. Remove whitespace from each line
        """
        lines = re.split(r"\n", text.strip())
        lines = [line for line in lines if line.strip()]  # remove empty lines
        # Use regular expression to remove the numbers and dots at the beginning of
        # each line
        return [re.sub(r"^\s*\d+\.\s*", "", line).strip() for line in lines]

    @staticmethod
    def _parse_number(text: str, importance_weight: Optional[float] = None) -> float:
        """Parse a number from a string."""
        match = re.search(r"^\D*(\d+)", text)
        if match:
            score = float(match.group(1))
            if importance_weight is not None:
                score = (score / 10) * importance_weight
            return score
        else:
            return 0.0


class LLMInsightExtractor(BaseLLMCaller, InsightExtractor[T]):
    """LLM Insight Extractor.

    Get high-level insights from memories.
    """

    prompt: str = (
        "There are some memories: {content}\nCan you infer from the "
        "above memories the high-level insight for this person's character? The insight"
        " needs to be significantly different from the content and structure of the "
        "original memories.Respond in one sentence.\n\n"
        "Results:"
    )

    async def extract_insights(
        self,
        memory_fragment: T,
        llm_client: Optional[LLMClient] = None,
    ) -> InsightMemoryFragment[T]:
        """Extract insights from memory fragments.

        Args:
            memory_fragment(T): Memory fragment
            llm_client(Optional[LLMClient]): LLM client

        Returns:
            InsightMemoryFragment: The insights of the memory fragment.
        """
        insights_str: str = await self.call_llm(
            self.prompt, llm_client, content=memory_fragment.raw_observation
        )
        insights_list = self._parse_list(insights_str)
        return InsightMemoryFragment(memory_fragment, insights_list)


class LLMImportanceScorer(BaseLLMCaller, ImportanceScorer[T]):
    """LLM Importance Scorer.

    Score the importance of memories.
    """

    prompt: str = (
        "Please give an importance score between 1 to 10 for the following "
        "observation. Higher score indicates the observation is more important. More "
        "rules that should be followed are:"
        "\n(1): Learning experience of a certain skill is important"
        "\n(2): The occurrence of a particular event is important"
        "\n(3): User thoughts and emotions matter"
        "\n(4): More informative indicates more important."
        "Please respond with a single integer."
        "\nObservation:{content}"
        "\nRating:"
    )

    async def score_importance(
        self,
        memory_fragment: T,
        llm_client: Optional[LLMClient] = None,
    ) -> float:
        """Score the importance of memory fragments.

        Args:
            memory_fragment(T): Memory fragment
            llm_client(Optional[LLMClient]): LLM client

        Returns:
            float: The importance score of the memory fragment.
        """
        score: str = await self.call_llm(
            self.prompt, llm_client, content=memory_fragment.raw_observation
        )
        return self._parse_number(score)
