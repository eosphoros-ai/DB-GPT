import logging

from pilot.out_parser.base import BaseOutputParser, T

logger = logging.getLogger(__name__)


class DocChatOutputParser(BaseOutputParser):
    def parse_prompt_response(self, model_out_text):
        # TODO 针对结果做一些修正和数据转化
        return model_out_text

    def parse_view_response(self, ai_text, data) -> str:
        return ai_text

    def get_format_instructions(self) -> str:
        pass
