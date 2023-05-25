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


class BaseOutputParser(ABC):
    """Class to parse the output of an LLM call.

    Output parsers help structure language model responses.
    """

    def __init__(self, sep: str, is_stream_out: bool):
        self.sep = sep
        self.is_stream_out = is_stream_out

    # TODO 后续和模型绑定
    def _parse_model_stream_resp(self, response, sep: str):
        pass

    def _parse_model_nostream_resp(self, response, sep: str):
        text = response.text.strip()
        text = text.rstrip()
        text = text.lower()
        respObj = json.loads(text)

        xx = respObj["response"]
        xx = xx.strip(b"\x00".decode())
        respObj_ex = json.loads(xx)
        if respObj_ex["error_code"] == 0:
            all_text = respObj_ex["text"]
            ### 解析返回文本，获取AI回复部分
            tmpResp = all_text.split(sep)
            last_index = -1
            for i in range(len(tmpResp)):
                if tmpResp[i].find("assistant:") != -1:
                    last_index = i
            ai_response = tmpResp[last_index]
            ai_response = ai_response.replace("assistant:", "")
            ai_response = ai_response.replace("\n", "")
            ai_response = ai_response.replace("\_", "_")
            ai_response = ai_response.replace("\*", "*")
            print("un_stream clear response:{}", ai_response)
            return ai_response
        else:
            raise ValueError("Model server error!code=" + respObj_ex["error_code"])

    def parse_model_server_out(self, response) -> str:
        """
        parse the model server http response
        Args:
            response:

        Returns:

        """
        if not self.is_stream_out:
            return self._parse_model_nostream_resp(response, self.sep)
        else:
            return self._parse_model_stream_resp(response, self.sep)

    def parse_prompt_response(self, model_out_text) -> T:
        """
        parse model out text to prompt define response
        Args:
            model_out_text:

        Returns:

        """
        pass

    def parse_view_response(self, ai_text) -> str:
        """
        parse the ai response info to user view
        Args:
            text:

        Returns:

        """
        pass

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
