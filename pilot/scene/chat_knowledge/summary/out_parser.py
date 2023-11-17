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
    def parse_model_nostream_resp(self, response: ResponseTye, sep: str) -> str:
        ### tool out data to table view
        resp_obj_ex = _parse_model_response(response)
        if isinstance(resp_obj_ex, str):
            resp_obj_ex = json.loads(resp_obj_ex)
        if resp_obj_ex["error_code"] == 0:
            all_text = resp_obj_ex["text"]
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
            raise ValueError("Model server error!code=" + resp_obj_ex["error_code"])
