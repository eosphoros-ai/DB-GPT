"""General prompt helper that can help deal with LLM context window token limitations.

At its core, it calculates available context size by starting with the context window
size of an LLM and reserve token space for the prompt template, and the output.

It provides utility for "repacking" text chunks (retrieved from index) to maximally
make use of the available context window (and thereby reducing the number of LLM calls
needed), or truncating them so that they fit in a single LLM call.
"""

import logging
from string import Formatter
from typing import Callable, List, Optional, Sequence, Set

from dbgpt._private.llm_metadata import LLMMetadata
from dbgpt._private.pydantic import BaseModel, Field, PrivateAttr
from dbgpt.core.interface.prompt import get_template_vars
from dbgpt.rag.text_splitter.token_splitter import TokenTextSplitter
from dbgpt.util.global_helper import globals_helper

DEFAULT_PADDING = 5
DEFAULT_CHUNK_OVERLAP_RATIO = 0.1

DEFAULT_CONTEXT_WINDOW = 3000  # tokens
DEFAULT_NUM_OUTPUTS = 256  # tokens

logger = logging.getLogger(__name__)


class PromptHelper(BaseModel):
    """Prompt helper.

    General prompt helper that can help deal with LLM context window token limitations.

    At its core, it calculates available context size by starting with the context
    window size of an LLM and reserve token space for the prompt template, and the
    output.

    It provides utility for "repacking" text chunks (retrieved from index) to maximally
    make use of the available context window (and thereby reducing the number of LLM
    calls needed), or truncating them so that they fit in a single LLM call.

    Args:
        context_window (int):                   Context window for the LLM.
        num_output (int):                       Number of outputs for the LLM.
        chunk_overlap_ratio (float):            Chunk overlap as a ratio of chunk size
        chunk_size_limit (Optional[int]):         Maximum chunk size to use.
        tokenizer (Optional[Callable[[str], List]]): Tokenizer to use.
        separator (str):                        Separator for text splitter

    """

    context_window: int = Field(
        default=DEFAULT_CONTEXT_WINDOW,
        description="The maximum context size that will get sent to the LLM.",
    )
    num_output: int = Field(
        default=DEFAULT_NUM_OUTPUTS,
        description="The amount of token-space to leave in input for generation.",
    )
    chunk_overlap_ratio: float = Field(
        default=DEFAULT_CHUNK_OVERLAP_RATIO,
        description="The percentage token amount that each chunk should overlap.",
    )
    chunk_size_limit: Optional[int] = Field(description="The maximum size of a chunk.")
    separator: str = Field(
        default=" ", description="The separator when chunking tokens."
    )

    _tokenizer: Callable[[str], List] = PrivateAttr()

    def __init__(
        self,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        num_output: int = DEFAULT_NUM_OUTPUTS,
        chunk_overlap_ratio: float = DEFAULT_CHUNK_OVERLAP_RATIO,
        chunk_size_limit: Optional[int] = None,
        tokenizer: Optional[Callable[[str], List]] = None,
        separator: str = " ",
    ) -> None:
        """Init params."""
        if chunk_overlap_ratio > 1.0 or chunk_overlap_ratio < 0.0:
            raise ValueError("chunk_overlap_ratio must be a float between 0. and 1.")

        # TODO: make configurable
        self._tokenizer = tokenizer or globals_helper.tokenizer

        super().__init__(
            context_window=context_window,
            num_output=num_output,
            chunk_overlap_ratio=chunk_overlap_ratio,
            chunk_size_limit=chunk_size_limit,
            separator=separator,
        )

    def token_count(self, prompt_template: str) -> int:
        """Get token count of prompt template."""
        empty_prompt_txt = get_empty_prompt_txt(prompt_template)
        return len(self._tokenizer(empty_prompt_txt))

    @classmethod
    def from_llm_metadata(
        cls,
        llm_metadata: LLMMetadata,
        chunk_overlap_ratio: float = DEFAULT_CHUNK_OVERLAP_RATIO,
        chunk_size_limit: Optional[int] = None,
        tokenizer: Optional[Callable[[str], List]] = None,
        separator: str = " ",
    ) -> "PromptHelper":
        """Create from llm predictor.

        This will autofill values like context_window and num_output.

        """
        context_window = llm_metadata.context_window
        if llm_metadata.num_output == -1:
            num_output = DEFAULT_NUM_OUTPUTS
        else:
            num_output = llm_metadata.num_output

        return cls(
            context_window=context_window,
            num_output=num_output,
            chunk_overlap_ratio=chunk_overlap_ratio,
            chunk_size_limit=chunk_size_limit,
            tokenizer=tokenizer,
            separator=separator,
        )

    @classmethod
    def class_name(cls) -> str:
        return "PromptHelper"

    def _get_available_context_size(self, template: str) -> int:
        """Get available context size.

        This is calculated as:
            available context window = total context window
                - input (partially filled prompt)
                - output (room reserved for response)

        Notes:
        - Available context size is further clamped to be non-negative.
        """
        empty_prompt_txt = get_empty_prompt_txt(template)
        num_empty_prompt_tokens = len(self._tokenizer(empty_prompt_txt))
        context_size_tokens = (
            self.context_window - num_empty_prompt_tokens - self.num_output
        )
        if context_size_tokens < 0:
            raise ValueError(
                f"Calculated available context size {context_size_tokens} was"
                " not non-negative."
            )
        return context_size_tokens

    def _get_available_chunk_size(
        self, prompt_template: str, num_chunks: int = 1, padding: int = 5
    ) -> int:
        """Get available chunk size.

        This is calculated as:
            available chunk size = available context window  // number_chunks
                - padding

        Notes:
        - By default, we use padding of 5 (to save space for formatting needs).
        - Available chunk size is further clamped to chunk_size_limit if specified.
        """
        available_context_size = self._get_available_context_size(prompt_template)
        result = available_context_size // num_chunks - padding
        if self.chunk_size_limit is not None:
            result = min(result, self.chunk_size_limit)
        return result

    def get_text_splitter_given_prompt(
        self,
        prompt_template: str,
        num_chunks: int = 1,
        padding: int = DEFAULT_PADDING,
    ) -> TokenTextSplitter:
        """Get text splitter configured to maximally pack available context window,
        taking into account of given prompt, and desired number of chunks.
        """
        chunk_size = self._get_available_chunk_size(
            prompt_template, num_chunks, padding=padding
        )
        if chunk_size <= 0:
            raise ValueError(f"Chunk size {chunk_size} is not positive.")
        chunk_overlap = int(self.chunk_overlap_ratio * chunk_size)
        return TokenTextSplitter(
            separator=self.separator,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            tokenizer=self._tokenizer,
        )

    def repack(
        self,
        prompt_template: str,
        text_chunks: Sequence[str],
        padding: int = DEFAULT_PADDING,
    ) -> List[str]:
        """Repack text chunks to fit available context window.

        This will combine text chunks into consolidated chunks
        that more fully "pack" the prompt template given the context_window.

        """
        text_splitter = self.get_text_splitter_given_prompt(
            prompt_template, padding=padding
        )
        combined_str = "\n\n".join([c.strip() for c in text_chunks if c.strip()])
        return text_splitter.split_text(combined_str)


def get_empty_prompt_txt(template: str) -> str:
    """Get empty prompt text.

    Substitute empty strings in parts of the prompt that have
    not yet been filled out. Skip variables that have already
    been partially formatted. This is used to compute the initial tokens.

    """
    # partial_kargs = prompt.kwargs

    partial_kargs = {}
    template_vars = get_template_vars(template)
    empty_kwargs = {v: "" for v in template_vars if v not in partial_kargs}
    all_kwargs = {**partial_kargs, **empty_kwargs}
    prompt = template.format(**all_kwargs)
    return prompt
