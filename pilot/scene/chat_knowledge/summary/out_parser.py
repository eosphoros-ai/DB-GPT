import json
import logging
import re
from typing import List, Tuple

from pilot.out_parser.base import BaseOutputParser, T
from pilot.configs.config import Config

CFG = Config()


logger = logging.getLogger(__name__)


class ExtractSummaryParser(BaseOutputParser):
    def __init__(self, sep: str, is_stream_out: bool):
        super().__init__(sep=sep, is_stream_out=is_stream_out)

    def parse_prompt_response(
        self, response, max_length: int = 128
    ) -> List[Tuple[str, str, str]]:
        # clean_str = super().parse_prompt_response(response)
        print("clean prompt response:", response)
        return response

    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        return data
