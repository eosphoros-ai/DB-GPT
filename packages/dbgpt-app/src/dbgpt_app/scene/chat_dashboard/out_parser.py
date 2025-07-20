import json
import logging
from typing import List, NamedTuple

from dbgpt.core.interface.output_parser import BaseOutputParser
from dbgpt_app.scene import ChatScene


class ChartItem(NamedTuple):
    sql: str
    title: str
    thoughts: str
    showcase: str


logger = logging.getLogger(__name__)


class ChatDashboardOutputParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool = False, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)

        try:
            response = json.loads(clean_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}. Attempting to clean and retry.")
            cleaned_str = self._clean_json_string(clean_str)
            try:
                response = json.loads(cleaned_str)
            except json.JSONDecodeError:
                logger.warning("JSON cleaning failed. Attempting fallback extraction.")
                response = self._extract_json_fallback(clean_str)
                if response is None:
                    raise ValueError(f"Unable to parse JSON from response: {clean_str}")

        chart_items: List[ChartItem] = []
        if not isinstance(response, list):
            response = [response]
        for item in response:
            chart_items.append(
                ChartItem(
                    item["sql"].replace("\\", " "),
                    item["title"],
                    item["thoughts"],
                    item["showcase"],
                )
            )
        return chart_items

    def _clean_json_string(self, json_str: str) -> str:
        """Clean common JSON formatting issues."""
        # Remove leading/trailing whitespace
        json_str = json_str.strip()

        # Remove markdown code blocks if present
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            if len(lines) > 1:
                # Remove first line (```json or ```)
                json_str = "\n".join(lines[1:])
                # Remove last line if it's just ```
                if json_str.strip().endswith("```"):
                    json_str = json_str.strip()[:-3]

        # Fix common escaping issues
        json_str = json_str.replace('\\"', '"')
        json_str = json_str.replace("\\\\", "\\")

        return json_str.strip()

    def _extract_json_fallback(self, text: str) -> dict:
        """Extract JSON using regex as fallback."""
        import re

        # Look for JSON-like structures
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        return None

    def parse_view_response(self, speak, data, prompt_response) -> str:
        return json.dumps(data.prepare_dict(), ensure_ascii=False)

    @property
    def _type(self) -> str:
        return ChatScene.ChatDashboard.value
