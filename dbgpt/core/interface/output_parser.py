"""The output parser is used to parse the output of an LLM call.

TODO: Make this more general and clear.
"""

from __future__ import annotations

import json
import logging
from abc import ABC
from dataclasses import asdict
from typing import Any, TypeVar, Union

from dbgpt.core import ModelOutput
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    OperatorType,
    ViewMetadata,
)
from dbgpt.util.i18n_utils import _

T = TypeVar("T")
ResponseTye = Union[str, bytes, ModelOutput]

logger = logging.getLogger(__name__)


class BaseOutputParser(MapOperator[ModelOutput, Any], ABC):
    """Class to parse the output of an LLM call.

    Output parsers help structure language model responses.
    """

    metadata = ViewMetadata(
        label=_("Base Output Operator"),
        name="base_output_operator",
        operator_type=OperatorType.TRANSFORM_STREAM,
        category=OperatorCategory.OUTPUT_PARSER,
        description=_("The base LLM out parse."),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Model Output"),
                "model_output",
                ModelOutput,
                is_list=True,
                description=_("The model output of upstream."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Model Output"),
                "model_output",
                str,
                is_list=True,
                description=_("The model output after parsing."),
            )
        ],
    )

    def __init__(self, is_stream_out: bool = True, **kwargs):
        """Create a new output parser."""
        super().__init__(**kwargs)
        self.is_stream_out = is_stream_out
        self.data_schema = None

    def update(self, data_schema):
        """Update the data schema.

        TODO: Remove this method.
        """
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
        """Parse the output of an LLM call.

        Args:
            chunk (ResponseTye): The output of an LLM call.
            skip_echo_len (int): The length of the prompt to skip.
        """
        data = _parse_model_response(chunk)
        # TODO: Multi mode output handler, rewrite this for multi model, use adapter
        #  mode.

        model_context = data.get("model_context")
        has_echo = False
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
        """Parse the output of an LLM call."""
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
            ai_response = ai_response.replace("\\_", "_")
            ai_response = ai_response.replace("\\*", "*")
            ai_response = ai_response.replace("\t", "")

            # ai_response = ai_response.strip().replace("\\n", " ").replace("\n", " ")
            # print("un_stream ai response:", ai_response)
            return ai_response
        else:
            raise ValueError(
                f"Model server error!code={resp_obj_ex['error_code']}, error msg is "
                f"{resp_obj_ex['text']}"
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
        except Exception:
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
        except Exception:
            return ""

    def parse_prompt_response(self, model_out_text) -> Any:
        """Parse model out text to prompt define response.

        Args:
            model_out_text: The output of an LLM call.

        Returns:
            Any: The parsed output of an LLM call.
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
            .replace("\\_", "_")
        )
        cleaned_output = self._illegal_json_ends(cleaned_output)
        return cleaned_output

    def parse_view_response(
        self, ai_text, data, parse_prompt_response: Any = None
    ) -> str:
        """Parse the AI response info to user view.

        Args:
            ai_text (str): The output of an LLM call.
            data (dict): The data has been handled by some scene.
            parse_prompt_response (Any): The prompt response has been parsed.

        Returns:
            str: The parsed output of an LLM call.

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
            return self.parse_model_nostream_resp(input_value, "#####################")


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
    """Parse the SQL output of an LLM call."""

    metadata = ViewMetadata(
        label=_("SQL Output Parser"),
        name="default_sql_output_parser",
        category=OperatorCategory.OUTPUT_PARSER,
        description=_("Parse the SQL output of an LLM call."),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Model Output"),
                "model_output",
                ModelOutput,
                description=_("The model output of upstream."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Dict SQL Output"),
                "dict",
                dict,
                description=_("The dict output after parsing."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, is_stream_out: bool = False, **kwargs):
        """Create a new SQL output parser."""
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_model_nostream_resp(self, response: ResponseTye, sep: str):
        """Parse the output of an LLM call."""
        model_out_text = super().parse_model_nostream_resp(response, sep)
        clean_str = super().parse_prompt_response(model_out_text)
        return json.loads(clean_str, strict=True)


class SQLListOutputParser(BaseOutputParser):
    """Parse the SQL list output of an LLM call."""

    metadata = ViewMetadata(
        label=_("SQL List Output Parser"),
        name="default_sql_list_output_parser",
        category=OperatorCategory.OUTPUT_PARSER,
        description=_(
            "Parse the SQL list output of an LLM call, mostly used for dashboard."
        ),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Model Output"),
                "model_output",
                ModelOutput,
                description=_("The model output of upstream."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("List SQL Output"),
                "list",
                dict,
                is_list=True,
                description=_("The list output after parsing."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, is_stream_out: bool = False, **kwargs):
        """Create a new SQL list output parser."""
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_model_nostream_resp(self, response: ResponseTye, sep: str):
        """Parse the output of an LLM call."""
        from dbgpt.util.json_utils import find_json_objects

        model_out_text = super().parse_model_nostream_resp(response, sep)
        json_objects = find_json_objects(model_out_text)
        json_count = len(json_objects)
        if json_count < 1:
            raise ValueError("Unable to obtain valid output.")

        parsed_json_list = json_objects[0]
        if not isinstance(parsed_json_list, list):
            if isinstance(parsed_json_list, dict):
                return [parsed_json_list]
            else:
                raise ValueError("Invalid output format.")
        return parsed_json_list
