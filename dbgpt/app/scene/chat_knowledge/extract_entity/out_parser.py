import logging
from typing import Set

from dbgpt.core.interface.output_parser import BaseOutputParser

logger = logging.getLogger(__name__)


class ExtractEntityParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_prompt_response(self, response, max_length: int = 128) -> Set[str]:
        lowercase = True
        # clean_str = super().parse_prompt_response(response)
        print("clean prompt response:", response)

        results = []
        response = response.strip()  # Strip newlines from responses.

        if response.startswith("KEYWORDS:"):
            response = response[len("KEYWORDS:") :]

        keywords = response.split(",")
        for k in keywords:
            rk = k
            if lowercase:
                rk = rk.lower()
            results.append(rk.strip())

        return set(results)

    def parse_view_response(self, speak, data) -> str:
        return data
