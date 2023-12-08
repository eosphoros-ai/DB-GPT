import logging
from typing import List, Tuple

from dbgpt.core.interface.output_parser import BaseOutputParser, ResponseTye

logger = logging.getLogger(__name__)


class ExtractSummaryParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_prompt_response(
        self, response, max_length: int = 128
    ) -> List[Tuple[str, str, str]]:
        # clean_str = super().parse_prompt_response(response)
        print("clean prompt response:", response)
        return response

    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        return data

    def parse_model_nostream_resp(self, response: ResponseTye, sep: str) -> str:
        try:
            return super().parse_model_nostream_resp(response, sep)
        except Exception as e:
            return str(e)
