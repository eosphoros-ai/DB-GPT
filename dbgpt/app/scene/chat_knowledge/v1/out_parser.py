import logging
from dbgpt.core.interface.output_parser import BaseOutputParser, T


logger = logging.getLogger(__name__)


class NormalChatOutputParser(BaseOutputParser):
    def parse_prompt_response(self, model_out_text) -> T:
        return model_out_text

    def get_format_instructions(self) -> str:
        pass
