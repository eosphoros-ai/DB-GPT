import json
import logging
from typing import Set

from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.config import Config

CFG = Config()


logger = logging.getLogger(__name__)


class ExtractEntityParser(BaseOutputParser):
    def __init__(self, sep: str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out)

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
