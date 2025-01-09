"""Code operators for DB-GPT.

The code will be executed in a sandbox environment, which is isolated from the host
system. You can limit the memory and file system access of the code execution.
"""

import json
import logging
import os

from dbgpt.core import ModelRequest
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    OptionValue,
    Parameter,
    ViewMetadata,
    ui,
)
from dbgpt.util.code.server import get_code_server
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)

_FN_PYTHON_MAP = """
import os
import json
import lyric_task
from lyric_py_task.imports import msgpack

def fn_map(args: dict[str, any]) -> dict[str, any]:
    text = args.get("text")
    return {
        "text": text,
        "key0": "customized key",
        "key1": "hello, world",
        "key2": [1, 2, 3],
        "key3": {"a": 1, "b": 2},
    }
"""

_FN_JAVASCRIPT_MAP = """
function fn_map(args) {
    var text = args.text;
    return {
        text: text,
        key0: "customized key",
        key1: "hello, world",
        key2: [1, 2, 3],
        key3: {a: 1, b: 2},
    };
}
"""


class CodeMapOperator(MapOperator[dict, dict]):
    metadata = ViewMetadata(
        label=_("Code Map Operator"),
        name="default_code_map_operator",
        description=_(
            "Handle input dictionary with code and return output dictionary after execution."
        ),
        category=OperatorCategory.CODE,
        parameters=[
            Parameter.build_from(
                _("Code Editor"),
                "code",
                type=str,
                optional=True,
                default=_FN_PYTHON_MAP,
                placeholder=_("Please input your code"),
                description=_("The code to be executed."),
                ui=ui.UICodeEditor(
                    language="python",
                ),
            ),
            Parameter.build_from(
                _("Language"),
                "lang",
                type=str,
                optional=True,
                default="python",
                placeholder=_("Please select the language"),
                description=_("The language of the code."),
                options=[
                    OptionValue(label="Python", name="python", value="python"),
                    OptionValue(
                        label="JavaScript", name="javascript", value="javascript"
                    ),
                ],
                ui=ui.UISelect(),
            ),
            Parameter.build_from(
                _("Call Name"),
                "call_name",
                type=str,
                optional=True,
                default="fn_map",
                placeholder=_("Please input the call name"),
                description=_("The call name of the function."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Input Data"),
                "input",
                type=dict,
                description=_("The input dictionary."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Output Data"),
                "output",
                type=dict,
                description=_("The output dictionary."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        code: str = _FN_PYTHON_MAP,
        lang: str = "python",
        call_name: str = "fn_map",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.code = code
        self.lang = lang
        self.call_name = call_name

    async def map(self, input_value: dict) -> dict:
        exec_input_data_bytes = json.dumps(input_value).encode("utf-8")
        code_server = await get_code_server()
        result = await code_server.exec1(
            self.code, exec_input_data_bytes, call_name=self.call_name, lang=self.lang
        )
        logger.info(f"Code execution result: {result}")
        return result.output


_REQ_BUILD_PY_FUNC = """
import os

def fn_map(args: dict[str, any]) -> dict[str, any]:

    llm_model = args.get("model", os.getenv("DBGPT_RUNTIME_LLM_MODEL"))
    messages: str | list[str] = args.get("messages", [])
    if isinstance(messages, str):
        human_message = messages
    else:
        human_message = messages[0]
        
    temperature = float(args.get("temperature") or 0.5)
    max_new_tokens = int(args.get("max_new_tokens") or 2048)
    conv_uid = args.get("conv_uid", "")
    print("Conv uid is: ", conv_uid)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "human", "content": human_message}
    ]
    return {
        "model": llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_new_tokens": max_new_tokens
    }
"""

_REQ_BUILD_JS_FUNC = """
function fn_map(args) {
    var llm_model = args.model || "chatgpt_proxyllm";
    var messages = args.messages || [];
    var human_message = messages[0];
    var temperature = parseFloat(args.temperature) || 0.5;
    var max_new_tokens = parseInt(args.max_new_tokens) || 2048;
    var conv_uid = args.conv_uid || "";
    console.log("Conv uid is: ", conv_uid);
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "human", "content": human_message}
    ];
    return {
        model: llm_model,
        messages: messages,
        temperature: temperature,
        max_new_tokens: max_new_tokens
    };
}
"""


class CodeDictToModelRequestOperator(MapOperator[dict, ModelRequest]):
    metadata = ViewMetadata(
        label=_("Code Dict to Model Request Operator"),
        name="default_code_dict_to_model_request_operator",
        description=_(
            "Handle input dictionary with code and return output ModelRequest after execution."
        ),
        category=OperatorCategory.CODE,
        parameters=[
            Parameter.build_from(
                _("Code Editor"),
                "code",
                type=str,
                optional=True,
                default=_REQ_BUILD_PY_FUNC,
                placeholder=_("Please input your code"),
                description=_("The code to be executed."),
                ui=ui.UICodeEditor(
                    language="python",
                ),
            ),
            Parameter.build_from(
                _("Language"),
                "lang",
                type=str,
                optional=True,
                default="python",
                placeholder=_("Please select the language"),
                description=_("The language of the code."),
                options=[
                    OptionValue(label="Python", name="python", value="python"),
                    OptionValue(
                        label="JavaScript", name="javascript", value="javascript"
                    ),
                ],
                ui=ui.UISelect(),
            ),
            Parameter.build_from(
                _("Call Name"),
                "call_name",
                type=str,
                optional=True,
                default="fn_map",
                placeholder=_("Please input the call name"),
                description=_("The call name of the function."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Input Data"),
                "input",
                type=dict,
                description=_("The input dictionary."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Output Data"),
                "output",
                type=ModelRequest,
                description=_("The output ModelRequest."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        code: str = _REQ_BUILD_PY_FUNC,
        lang: str = "python",
        call_name: str = "fn_map",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.code = code
        self.lang = lang
        self.call_name = call_name

    async def map(self, input_value: dict) -> ModelRequest:
        from lyric import PyTaskFsConfig, PyTaskMemoryConfig, PyTaskResourceConfig

        exec_input_data_bytes = json.dumps(input_value).encode("utf-8")
        code_server = await get_code_server()
        model_name = os.getenv("LLM_MODEL")

        fs = PyTaskFsConfig(
            preopens=[
                # Mount the /tmp directory to the /tmp directory in the sandbox
                # Directory permissions are set to 3 (read and write)
                # File permissions are set to 3 (read and write)
                ("/tmp", "/tmp", 3, 3),
                # Mount the current directory to the /home directory in the sandbox
                # Directory and file permissions are set to 1 (read)
                (".", "/home", 1, 1),
            ]
        )
        memory = PyTaskMemoryConfig(memory_limit=50 * 1024 * 1024)  # 50MB in bytes
        resources = PyTaskResourceConfig(
            fs=fs,
            memory=memory,
            env_vars=[
                ("DBGPT_RUNTIME_LLM_MODEL", model_name),
            ],
        )
        result = await code_server.exec1(
            self.code,
            exec_input_data_bytes,
            call_name=self.call_name,
            lang=self.lang,
            resources=resources,
        )
        logger.info(f"Code execution result: {result}")
        if result.exit_code != 0:
            raise RuntimeError(f"Code execution failed: {result.logs}")

        if not result.output:
            raise RuntimeError(f"Code execution failed: {result.logs}")

        if not isinstance(result.output, dict):
            raise RuntimeError(
                f"Code execution failed, invalid output: {result.output}"
            )
        logger.info(f"Code execution result: {result}")
        return ModelRequest(**result.output)
