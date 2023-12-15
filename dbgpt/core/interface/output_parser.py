from __future__ import annotations

import json
from abc import ABC
import logging
from dataclasses import asdict
from typing import Any, Dict, TypeVar, Union

from dbgpt.core.awel import MapOperator
from dbgpt.core import ModelOutput

T = TypeVar("T")
ResponseTye = Union[str, bytes, ModelOutput]

logger = logging.getLogger(__name__)


class BaseOutputParser(MapOperator[ModelOutput, Any], ABC):
    """Class to parse the output of an LLM call.

    Output parsers help structure language model responses.
    """

    def __init__(self, is_stream_out: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.is_stream_out = is_stream_out
        self.data_schema = None

    def update(self, data_schema):
        self.data_schema = data_schema

    def __post_process_code(self, code):
        sep = "\n```"
        if sep in code:
            blocks = code.split(sep)
            if len(blocks) % 2 == 1:
                for i in range(1, len(blocks), 2):
                    blocks[i] = blocks[i].replace("\\_", "_")
            code = sep.join(blocks)
        return code

    def parse_model_stream_resp_ex(self, chunk: ResponseTye, skip_echo_len):
        data = _parse_model_response(chunk)
        """ TODO Multi mode output handler,  rewrite this for multi model, use adapter mode.
        """
        model_context = data.get("model_context")
        has_echo = True
        if model_context and "prompt_echo_len_char" in model_context:
            prompt_echo_len_char = int(model_context.get("prompt_echo_len_char", -1))
            has_echo = bool(model_context.get("echo", False))
            if prompt_echo_len_char != -1:
                skip_echo_len = prompt_echo_len_char

        if data.get("error_code", 0) == 0:
            if has_echo:
                # TODO Judging from model_context
                output = data["text"][skip_echo_len:].strip()
            else:
                output = data["text"].strip()

            output = self.__post_process_code(output)
            return output
        else:
            output = data["text"] + f" (error_code: {data['error_code']})"
            return output

    def parse_model_nostream_resp(self, response: ResponseTye, sep: str):
        resp_obj_ex = _parse_model_response(response)
        if isinstance(resp_obj_ex, str):
            resp_obj_ex = json.loads(resp_obj_ex)
        if resp_obj_ex["error_code"] == 0:
            all_text = resp_obj_ex["text"]
            # Parse the returned text to get the AI reply part
            tmp_resp = all_text.split(sep)
            last_index = -1
            for i in range(len(tmp_resp)):
                if tmp_resp[i].find("assistant:") != -1:
                    last_index = i
            ai_response = tmp_resp[last_index]
            ai_response = ai_response.replace("assistant:", "")
            ai_response = ai_response.replace("Assistant:", "")
            ai_response = ai_response.replace("ASSISTANT:", "")
            ai_response = ai_response.replace("\_", "_")
            ai_response = ai_response.replace("\*", "*")
            ai_response = ai_response.replace("\t", "")

            ai_response = ai_response.strip().replace("\\n", " ").replace("\n", " ")
            print("un_stream ai response:", ai_response)
            return ai_response
        else:
            raise ValueError(
                f"""Model server error!code={resp_obj_ex["error_code"]}, errmsg is {resp_obj_ex["text"]}"""
            )

    def _illegal_json_ends(self, s):
        temp_json = s
        illegal_json_ends_1 = [", }", ",}"]
        illegal_json_ends_2 = ", ]", ",]"
        for illegal_json_end in illegal_json_ends_1:
            temp_json = temp_json.replace(illegal_json_end, " }")
        for illegal_json_end in illegal_json_ends_2:
            temp_json = temp_json.replace(illegal_json_end, " ]")
        return temp_json

    def _extract_json(self, s):
        try:
            # Get the dual-mode analysis first and get the maximum result
            temp_json_simple = self._json_interception(s)
            temp_json_array = self._json_interception(s, True)
            if len(temp_json_simple) > len(temp_json_array):
                temp_json = temp_json_simple
            else:
                temp_json = temp_json_array

            if not temp_json:
                temp_json = self._json_interception(s)

            temp_json = self._illegal_json_ends(temp_json)
            return temp_json
        except Exception as e:
            raise ValueError("Failed to find a valid json in LLM response！" + temp_json)

    def _json_interception(self, s, is_json_array: bool = False):
        try:
            if is_json_array:
                i = s.find("[")
                if i < 0:
                    return ""
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
                    return ""
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
        except Exception as e:
            return ""

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
            cleaned_output = self._extract_json(cleaned_output)

        if not cleaned_output or len(cleaned_output) <= 0:
            return model_out_text

        cleaned_output = (
            cleaned_output.strip()
            .replace("\\n", " ")
            .replace("\n", " ")
            .replace("\\", " ")
            .replace("\_", "_")
        )
        cleaned_output = self._illegal_json_ends(cleaned_output)
        return cleaned_output

    def parse_view_response(
        self, ai_text, data, parse_prompt_response: Any = None
    ) -> str:
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

    async def map(self, input_value: ModelOutput) -> Any:
        """Parse the output of an LLM call.

        Args:
            input_value (ModelOutput): The output of an LLM call.

        Returns:
            Any: The parsed output of an LLM call.
        """
        if self.current_dag_context.streaming_call:
            return self.parse_model_stream_resp_ex(input_value, 0)
        else:
            return self.parse_model_nostream_resp(input_value, "###")


def _parse_model_response(response: ResponseTye):
    if response is None:
        resp_obj_ex = ""
    elif isinstance(response, ModelOutput):
        resp_obj_ex = asdict(response)
    elif isinstance(response, str):
        resp_obj_ex = json.loads(response)
    elif isinstance(response, bytes):
        if b"\0" in response:
            response = response.replace(b"\0", b"")
        resp_obj_ex = json.loads(response.decode())
    else:
        raise ValueError(f"Unsupported response type {type(response)}")
    return resp_obj_ex


class SQLOutputParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool = False, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_model_nostream_resp(self, response: ResponseTye, sep: str):
        model_out_text = super().parse_model_nostream_resp(response, sep)
        clean_str = super().parse_prompt_response(model_out_text)
        return json.loads(clean_str, strict=True)
