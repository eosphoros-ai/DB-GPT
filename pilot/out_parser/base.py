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
from pilot.utils import build_logger
import re

from pydantic import BaseModel, Extra, Field, root_validator
from pilot.configs.model_config import LOGDIR
from pilot.configs.config import Config

T = TypeVar("T")
logger = build_logger("webserver", LOGDIR + "DbChatOutputParser.log")

CFG = Config()


class BaseOutputParser(ABC):
    """Class to parse the output of an LLM call.

    Output parsers help structure language model responses.
    """

    def __init__(self, sep: str, is_stream_out: bool = True):
        self.sep = sep
        self.is_stream_out = is_stream_out

    def __post_process_code(self, code):
        sep = "\n```"
        if sep in code:
            blocks = code.split(sep)
            if len(blocks) % 2 == 1:
                for i in range(1, len(blocks), 2):
                    blocks[i] = blocks[i].replace("\\_", "_")
            code = sep.join(blocks)
        return code

    def parse_model_stream_resp_ex(self, chunk, skip_echo_len):
        if b"\0" in chunk:
            chunk = chunk.replace(b"\0", b"")
        data = json.loads(chunk.decode())

        """ TODO Multi mode output handler,  rewrite this for multi model, use adapter mode.
        """
        if data.get("error_code", 0) == 0:
            if "vicuna" in CFG.LLM_MODEL:
                # output = data["text"][skip_echo_len + 11:].strip()
                output = data["text"][skip_echo_len:].strip()
            elif "guanaco" in CFG.LLM_MODEL:
                # NO stream output
                # output = data["text"][skip_echo_len + 2:].replace("<s>", "").strip()

                # stream out output
                output = data["text"][11:].replace("<s>", "").strip()

                # TODO gorilla and falcon output
            else:
                output = data["text"].strip()

            output = self.__post_process_code(output)
            return output
        else:
            output = data["text"] + f" (error_code: {data['error_code']})"
            return output

    # TODO 后续和模型绑定
    def parse_model_stream_resp(self, response, skip_echo_len):
        for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
            if chunk:
                data = json.loads(chunk.decode())

                """ TODO Multi mode output handler,  rewrite this for multi model, use adapter mode.
                """
                if data["error_code"] == 0:
                    if "vicuna" in CFG.LLM_MODEL or "guanaco" in CFG.LLM_MODEL:
                        output = data["text"][skip_echo_len:].strip()
                    else:
                        output = data["text"].strip()

                    output = self.__post_process_code(output)
                    yield output
                else:
                    output = data["text"] + f" (error_code: {data['error_code']})"
                    yield output

    def parse_model_nostream_resp(self, response, sep: str):
        resp_obj_ex = json.loads(response)
        if isinstance(resp_obj_ex, str):
            resp_obj_ex = json.loads(resp_obj_ex)
        if resp_obj_ex["error_code"] == 0:
            all_text = resp_obj_ex["text"]
            ### 解析返回文本，获取AI回复部分
            tmp_resp = all_text.split(sep)
            last_index = -1
            for i in range(len(tmp_resp)):
                if tmp_resp[i].find("assistant:") != -1:
                    last_index = i
            ai_response = tmp_resp[last_index]
            ai_response = ai_response.replace("assistant:", "")
            ai_response = ai_response.replace("Assistant:", "")
            ai_response = ai_response.replace("ASSISTANT:", "")
            ai_response = ai_response.replace("\n", " ")
            ai_response = ai_response.replace("\_", "_")
            ai_response = ai_response.replace("\*", "*")
            ai_response = ai_response.replace("\t", "")
            print("un_stream ai response:", ai_response)
            return ai_response
        else:
            raise ValueError("Model server error!code=" + resp_obj_ex["error_code"])

    def __illegal_json_ends(self, s):
        temp_json = s
        illegal_json_ends_1 = [", }", ",}"]
        illegal_json_ends_2 = ", ]", ",]"
        for illegal_json_end in illegal_json_ends_1:
            temp_json = temp_json.replace(illegal_json_end, " }")
        for illegal_json_end in illegal_json_ends_2:
            temp_json = temp_json.replace(illegal_json_end, " ]")
        return temp_json

    def __extract_json(self, s):
        temp_json = self.__json_interception(s, True)
        if not temp_json:
            temp_json = self.__json_interception(s)
        try:
            temp_json = self.__illegal_json_ends(temp_json)
            return temp_json
        except Exception as e:
            raise ValueError("Failed to find a valid json response！" + temp_json)

    def __json_interception(self, s, is_json_array: bool = False):
        if is_json_array:
            i = s.find("[")
            if i < 0:
                return None
            count = 1
            for j, c in enumerate(s[i + 1 :], start=i + 1):
                if c == "]":
                    count -= 1
                elif c == "[":
                    count += 1
                if count == 0:
                    break
            assert count == 0
            return s[i : j + 1]
        else:
            i = s.find("{")
            if i < 0:
                return None
            count = 1
            for j, c in enumerate(s[i + 1 :], start=i + 1):
                if c == "}":
                    count -= 1
                elif c == "{":
                    count += 1
                if count == 0:
                    break
            assert count == 0
            return s[i : j + 1]

    def parse_prompt_response(self, model_out_text) -> T:
        """
        parse model out text to prompt define response
        Args:
            model_out_text:

        Returns:

        """
        cleaned_output = model_out_text.rstrip()
        if "```json" in cleaned_output:
            _, cleaned_output = cleaned_output.split("```json")
        # if "```" in cleaned_output:
        #     cleaned_output, _ = cleaned_output.split("```")
        if cleaned_output.startswith("```json"):
            cleaned_output = cleaned_output[len("```json") :]
        if cleaned_output.startswith("```"):
            cleaned_output = cleaned_output[len("```") :]
        if cleaned_output.endswith("```"):
            cleaned_output = cleaned_output[: -len("```")]
        cleaned_output = cleaned_output.strip()
        if not cleaned_output.startswith("{") or not cleaned_output.endswith("}"):
            logger.info("illegal json processing:\n" + cleaned_output)
            cleaned_output = self.__extract_json(cleaned_output)
        cleaned_output = (
            cleaned_output.strip()
            .replace("\n", " ")
            .replace("\\n", " ")
            .replace("\\", " ")
        )
        cleaned_output = self.__illegal_json_ends(cleaned_output)
        return cleaned_output

    def parse_view_response(self, ai_text, data) -> str:
        """
        parse the ai response info to user view
        Args:
            text:

        Returns:

        """
        return ai_text

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
