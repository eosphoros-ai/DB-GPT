import logging
from dbgpt.core.interface.output_parser import BaseOutputParser

logger = logging.getLogger(__name__)


class NormalChatOutputParser(BaseOutputParser):
    def parse_prompt_response(self, model_out_text):
        clean_str = super().parse_prompt_response(model_out_text)
        print("clean prompt response:", clean_str)
        return clean_str

    def parse_view_response(self, ai_text, data) -> str:
        return ai_text

    def get_format_instructions(self) -> str:
        pass
