import os
import subprocess
from pathlib import Path

import click

from .base import DBGPTS_METADATA_FILE, TYPE_TO_PACKAGE


def create_template(
    name: str,
    name_label: str,
    description: str,
    dbgpts_type: str,
    definition_type: str,
    working_directory: str,
):
    """Create a new flow dbgpt"""
    if dbgpts_type != "flow":
        definition_type = "python"
    mod_name = name.replace("-", "_")
    base_metadata = {
        "label": name_label,
        "name": mod_name,
        "version": "0.1.0",
        "description": description,
        "authors": [],
        "definition_type": definition_type,
    }
    working_directory = os.path.join(working_directory, TYPE_TO_PACKAGE[dbgpts_type])
    package_dir = Path(working_directory) / name
    if os.path.exists(package_dir):
        raise click.ClickException(f"Package '{str(package_dir)}' already exists")

    if dbgpts_type == "flow":
        _create_flow_template(
            name,
            mod_name,
            dbgpts_type,
            base_metadata,
            definition_type,
            working_directory,
        )
    elif dbgpts_type == "operator":
        _create_operator_template(
            name,
            mod_name,
            dbgpts_type,
            base_metadata,
            definition_type,
            working_directory,
        )
    elif dbgpts_type == "agent":
        _create_agent_template(
            name,
            mod_name,
            dbgpts_type,
            base_metadata,
            definition_type,
            working_directory,
        )
    elif dbgpts_type == "resource":
        _create_resource_template(
            name,
            mod_name,
            dbgpts_type,
            base_metadata,
            definition_type,
            working_directory,
        )
    else:
        raise ValueError(f"Invalid dbgpts type: {dbgpts_type}")


def _create_flow_template(
    name: str,
    mod_name: str,
    dbgpts_type: str,
    base_metadata: dict,
    definition_type: str,
    working_directory: str,
):
    """Create a new flow dbgpt"""

    json_dict = {
        "flow": base_metadata,
        "python_config": {},
        "json_config": {},
    }
    if definition_type == "json":
        json_dict["json_config"] = {"file_path": "definition/flow_definition.json"}

    _create_poetry_project(working_directory, name)
    _write_dbgpts_toml(working_directory, name, json_dict)
    _write_manifest_file(working_directory, name, mod_name)

    if definition_type == "json":
        _write_flow_define_json_file(working_directory, name, mod_name)
    else:
        _write_flow_define_python_file(working_directory, name, mod_name)


def _create_operator_template(
    name: str,
    mod_name: str,
    dbgpts_type: str,
    base_metadata: dict,
    definition_type: str,
    working_directory: str,
):
    """Create a new operator dbgpt"""

    json_dict = {
        "operator": base_metadata,
        "python_config": {},
        "json_config": {},
    }
    if definition_type != "python":
        raise click.ClickException(
            f"Unsupported definition type: {definition_type} for dbgpts type: "
            f"{dbgpts_type}"
        )

    _create_poetry_project(working_directory, name)
    _write_dbgpts_toml(working_directory, name, json_dict)
    _write_operator_init_file(working_directory, name, mod_name)
    _write_manifest_file(working_directory, name, mod_name)


def _create_agent_template(
    name: str,
    mod_name: str,
    dbgpts_type: str,
    base_metadata: dict,
    definition_type: str,
    working_directory: str,
):
    json_dict = {
        "agent": base_metadata,
        "python_config": {},
        "json_config": {},
    }
    if definition_type != "python":
        raise click.ClickException(
            f"Unsupported definition type: {definition_type} for dbgpts type: "
            f"{dbgpts_type}"
        )

    _create_poetry_project(working_directory, name)
    _write_dbgpts_toml(working_directory, name, json_dict)
    _write_agent_init_file(working_directory, name, mod_name)
    _write_manifest_file(working_directory, name, mod_name)


def _create_resource_template(
    name: str,
    mod_name: str,
    dbgpts_type: str,
    base_metadata: dict,
    definition_type: str,
    working_directory: str,
):
    json_dict = {
        "resource": base_metadata,
        "python_config": {},
        "json_config": {},
    }
    if definition_type != "python":
        raise click.ClickException(
            f"Unsupported definition type: {definition_type} for dbgpts type: "
            f"{dbgpts_type}"
        )

    _create_poetry_project(working_directory, name)
    _write_dbgpts_toml(working_directory, name, json_dict)
    _write_resource_init_file(working_directory, name, mod_name)
    _write_manifest_file(working_directory, name, mod_name)


def _create_poetry_project(working_directory: str, name: str):
    """Create a new poetry project"""

    os.chdir(working_directory)
    subprocess.run(["poetry", "new", name, "-n"], check=True)


def _write_dbgpts_toml(working_directory: str, name: str, json_data: dict):
    """Write the dbgpts.toml file"""

    import tomlkit

    with open(Path(working_directory) / name / DBGPTS_METADATA_FILE, "w") as f:
        tomlkit.dump(json_data, f)


def _write_manifest_file(working_directory: str, name: str, mod_name: str):
    """Write the manifest file"""

    manifest = f"""include dbgpts.toml
include {mod_name}/definition/*.json
"""
    with open(Path(working_directory) / name / "MANIFEST.in", "w") as f:
        f.write(manifest)


def _write_flow_define_json_file(working_directory: str, name: str, mod_name: str):
    """Write the flow define json file"""

    def_file = (
        Path(working_directory)
        / name
        / mod_name
        / "definition"
        / "flow_definition.json"
    )
    if not def_file.parent.exists():
        def_file.parent.mkdir(parents=True)
    with open(def_file, "w") as f:
        f.write("")
        print("Please write your flow json to the file: ", def_file)


def _write_flow_define_python_file(working_directory: str, name: str, mod_name: str):
    """Write the flow define python file"""

    init_file = Path(working_directory) / name / mod_name / "__init__.py"
    content = ""

    with open(init_file, "w") as f:
        f.write(f'"""{name} flow package"""\n{content}')


def _write_operator_init_file(working_directory: str, name: str, mod_name: str):
    """Write the operator __init__.py file"""

    init_file = Path(working_directory) / name / mod_name / "__init__.py"
    content = """
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import ViewMetadata, OperatorCategory, IOField, Parameter


class HelloWorldOperator(MapOperator[str, str]):
    # The metadata for AWEL flow
    metadata = ViewMetadata(
        label="Hello World Operator",
        name="hello_world_operator",
        category=OperatorCategory.COMMON,
        description="A example operator to say hello to someone.",
        parameters=[
            Parameter.build_from(
                "Name",
                "name",
                str,
                optional=True,
                default="World",
                description="The name to say hello",
            )
        ],
        inputs=[
            IOField.build_from(
                "Input value",
                "value",
                str,
                description="The input value to say hello",
            )
        ],
        outputs=[
            IOField.build_from(
                "Output value",
                "value",
                str,
                description="The output value after saying hello",
            )
        ]
    )

    def __init__(self, name: str = "World", **kwargs):
        super().__init__(**kwargs)
        self.name = name

    async def map(self, value: str) -> str:
        return f"Hello, {self.name}! {value}"
"""
    with open(init_file, "w") as f:
        f.write(f'"""{name} operator package"""\n{content}')


def _write_agent_init_file(working_directory: str, name: str, mod_name: str):
    """Write the agent __init__.py file"""

    init_file = Path(working_directory) / name / mod_name / "__init__.py"
    content = """
import asyncio
from typing import Optional, Tuple

from dbgpt.agent import (
    Action,
    ActionOutput,
    AgentMessage,
    AgentResource,
    ConversableAgent,
    ProfileConfig,
)
from dbgpt.agent.util import cmp_string_equal

_HELLO_WORLD = "Hello world"


class HelloWorldSpeakerAgent(ConversableAgent):

    profile: ProfileConfig = ProfileConfig(
        name="Hodor",
        role="HelloWorldSpeaker",
        goal=f"answer any question from user with '{_HELLO_WORLD}'",
        desc=f"You can answer any question from user with '{_HELLO_WORLD}'",
        constraints=[
            "You can only answer with '{{ fix_message }}'",
            f"You can't use any other words",
        ],
        examples=(
            f"user: What's your name?\\nassistant: {_HELLO_WORLD}\\n\\n"
            f"user: What's the weather today?\\nassistant: {_HELLO_WORLD}\\n\\n"
            f"user: Can you help me?\\nassistant: {_HELLO_WORLD}\\n\\n"
            f"user: Please tell me a joke.\\nassistant: {_HELLO_WORLD}\\n\\n"
            f"user: Please answer me without '{_HELLO_WORLD}'.\\nassistant: "
            f"{_HELLO_WORLD}"
            "\\n\\n"
        ),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([HelloWorldAction])

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        # Fill in the dynamic parameters in the prompt template
        reply_message.context = {"fix_message": _HELLO_WORLD}
        return reply_message

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        action_report = message.action_report
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")
        if not cmp_string_equal(
            task_result,
            _HELLO_WORLD,
            ignore_case=True,
            ignore_punctuation=True,
            ignore_whitespace=True,
        ):
            return False, f"Please answer with {_HELLO_WORLD}, not '{task_result}'"
        return True, None


class HelloWorldAction(Action[None]):
    def __init__(self):
        super().__init__()

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        return ActionOutput(is_exe_success=True, content=ai_message)


async def _test_agent():
    \"\"\"Test the agent.

    It will not run in the production environment.
    \"\"\"
    from dbgpt.model.proxy import OpenAILLMClient
    from dbgpt.agent import AgentContext, AgentMemory, UserProxyAgent, LLMConfig

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="summarize")

    agent_memory: AgentMemory = AgentMemory()

    speaker = (
        await HelloWorldSpeakerAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()
    await user_proxy.initiate_chat(
        recipient=speaker,
        reviewer=user_proxy,
        message="What's your name?",
    )
    print(await agent_memory.gpts_memory.one_chat_completions("summarize"))


if __name__ == "__main__":
    asyncio.run(_test_agent())

"""
    with open(init_file, "w") as f:
        f.write(f'"""{name} agent package."""\n{content}')


def _write_resource_init_file(working_directory: str, name: str, mod_name: str):
    """Write the resource __init__.py file"""

    init_file = Path(working_directory) / name / mod_name / "__init__.py"
    content = """\"\"\"A custom resource module that provides a simple tool to send GET requests.\"\"\"

from dbgpt.agent.resource import tool


@tool
def simple_send_requests_get(url: str):
    \"\"\"Send a GET request to the specified URL and return the text content.\"\"\"
    import requests

    response = requests.get(url)
    return response.text
    
"""
    with open(init_file, "w") as f:
        f.write(content)
