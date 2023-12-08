import json
import logging
from typing import Dict, NamedTuple
from dbgpt.core.interface.output_parser import BaseOutputParser, T


logger = logging.getLogger(__name__)


class PluginAction(NamedTuple):
    command: Dict
    speak: str = ""
    thoughts: str = ""


class PluginChatOutputParser(BaseOutputParser):
    def parse_prompt_response(self, model_out_text) -> T:
        clean_json_str = super().parse_prompt_response(model_out_text)
        print(clean_json_str)
        if not clean_json_str:
            raise ValueError("model server response not have json!")
        try:
            response = json.loads(clean_json_str)
        except Exception as e:
            raise ValueError("model server out not fllow the prompt!")

        speak = ""
        thoughts = ""
        for key in sorted(response):
            if key.strip() == "command":
                command = response[key]
            if key.strip() == "thoughts":
                thoughts = response[key]
            if key.strip() == "speak":
                speak = response[key]
        return PluginAction(command, speak, thoughts)

    def parse_view_response(self, speak, data, prompt_response) -> str:
        ### tool out data to table view
        print(f"parse_view_response:{speak},{str(data)}")
        view_text = f"##### {speak}" + "\n" + str(data)
        return view_text

    def get_format_instructions(self) -> str:
        pass
