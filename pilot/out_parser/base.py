from __future__ import annotations
import json

from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from pydantic import BaseModel, Extra, Field, root_validator

from pilot.prompts.base import PromptValue

T = TypeVar("T")


class BaseOutputParser(BaseModel, ABC, Generic[T]):
    """Class to parse the output of an LLM call.

    Output parsers help structure language model responses.
    """

    def parse_model_nostream_resp(self, response, sep: str):
        text = response.text.strip()
        text = text.rstrip()
        respObj = json.loads(text)

        xx = respObj['response']
        xx = xx.strip(b'\x00'.decode())
        respObj_ex = json.loads(xx)
        if respObj_ex['error_code'] == 0:
            all_text = respObj_ex['text']
            ### 解析返回文本，获取AI回复部分
            tmpResp = all_text.split(sep)
            last_index = -1
            for i in range(len(tmpResp)):
                if tmpResp[i].find('ASSISTANT:') != -1:
                    last_index = i
            ai_response = tmpResp[last_index]
            ai_response = ai_response.replace("ASSISTANT:", "")
            ai_response = ai_response.replace("\n", "")
            ai_response = ai_response.replace("\_", "_")
            print("un_stream clear response:{}", ai_response)
            return ai_response
        else:
            raise ValueError("Model server error!code=" + respObj_ex['error_code']);

    @abstractmethod
    def parse(self, text: str) -> T:
        """Parse the output of an LLM call.

        A method which takes in a string (assumed output of language model )
        and parses it into some structure.

        Args:
            text: output of language model

        Returns:
            structured output
        """

    def parse_with_prompt(self, completion: str, prompt: PromptValue) -> Any:
        """Optional method to parse the output of an LLM call with a prompt.

        The prompt is largely provided in the event the OutputParser wants
        to retry or fix the output in some way, and needs information from
        the prompt to do so.

        Args:
            completion: output of language model
            prompt: prompt value

        Returns:
            structured output
        """
        return self.parse(completion)

    def get_format_instructions(self) -> str:
        """Instructions on how the LLM output should be formatted."""
        raise NotImplementedError

    @property
    def _type(self) -> str:
        """Return the type key."""
        raise NotImplementedError(
            f"_type property is not implemented in class {self.__class__.__name__}."
            " This is required for serialization."
        )

    def dict(self, **kwargs: Any) -> Dict:
        """Return dictionary representation of output parser."""
        output_parser_dict = super().dict()
        output_parser_dict["_type"] = self._type
        return output_parser_dict
