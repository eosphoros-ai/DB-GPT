from typing import Dict, NamedTuple
from dbgpt.core.interface.output_parser import BaseOutputParser


class PluginAction(NamedTuple):
    command: Dict
    speak: str = ""
    thoughts: str = ""


class PluginChatOutputParser(BaseOutputParser):
    def parse_view_response(self, speak, data, prompt_response) -> str:
        ### tool out data to table view
        print(f"parse_view_response:{speak},{str(data)}")
        view_text = f"##### {speak}" + "\n" + str(data)
        return view_text

    def get_format_instructions(self) -> str:
        pass
