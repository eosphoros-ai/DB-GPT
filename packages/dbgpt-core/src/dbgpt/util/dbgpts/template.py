import os
import shutil
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

    # Create project structure
    _create_project_structure(working_directory, name, base_metadata.get("description"))

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
    # Create project structure
    _create_project_structure(working_directory, name, base_metadata.get("description"))

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

    # Create project structure
    _create_project_structure(working_directory, name, base_metadata.get("description"))

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

    # Create project structure
    _create_project_structure(working_directory, name, base_metadata.get("description"))

    _write_dbgpts_toml(working_directory, name, json_dict)
    _write_resource_init_file(working_directory, name, mod_name)
    _write_manifest_file(working_directory, name, mod_name)


def _create_project_structure(
    working_directory: str, name: str, description: str = None
):
    """Create a new project using uv, poetry or manual file creation

    Args:
        working_directory (str): Directory to create the project in
        name (str): Name of the project
        description (str, optional): Project description

    Returns:
        bool: True if project created successfully
    """
    os.chdir(working_directory)

    # Try uv first
    if shutil.which("uv"):
        try:
            cmd = ["uv", "init", "--no-workspace"]

            if description:
                cmd.extend(["--description", description])

            cmd.append(name)

            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            click.echo("Warning: Failed to create project with uv, trying poetry...")

    # Try poetry next
    if shutil.which("poetry"):
        try:
            subprocess.run(["poetry", "new", name, "-n"], check=True)

            # If description provided, update pyproject.toml
            if description:
                pyproject_path = Path(working_directory) / name / "pyproject.toml"
                if pyproject_path.exists():
                    _update_pyproject_description(pyproject_path, description)

            return True
        except subprocess.CalledProcessError:
            click.echo(
                "Warning: Failed to create project with poetry, creating files "
                "manually..."
            )

    # Manual creation as fallback
    project_dir = Path(working_directory) / name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create basic project structure
    _create_manual_project_structure(project_dir, name, description)

    return True


def _update_pyproject_description(pyproject_path, description):
    """Update description in pyproject.toml file"""
    try:
        import tomlkit

        with open(pyproject_path, "r") as f:
            pyproject = tomlkit.parse(f.read())

        if "tool" in pyproject and "poetry" in pyproject["tool"]:
            pyproject["tool"]["poetry"]["description"] = description
        elif "project" in pyproject:
            pyproject["project"]["description"] = description

        with open(pyproject_path, "w") as f:
            f.write(tomlkit.dumps(pyproject))
    except Exception as e:
        click.echo(f"Warning: Failed to update description in pyproject.toml: {e}")


def _create_manual_project_structure(project_dir, name, description=None):
    """Create manual project structure with necessary files"""
    mod_name = name.replace("-", "_")

    # Create module directory
    module_dir = project_dir / mod_name
    module_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    with open(module_dir / "__init__.py", "w") as f:
        f.write(f'"""Main module for {name}."""\n\n')

    # Create pyproject.toml
    pyproject_content = f"""[project]
name = "{name}"
version = "0.1.0"
description = "{description or f"A {name} package"}"
readme = "README.md"
requires-python = ">=3.8"
dependencies = []

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
"""
    with open(project_dir / "pyproject.toml", "w") as f:
        f.write(pyproject_content)

    # Create README.md
    with open(project_dir / "README.md", "w") as f:
        f.write(f"# {name}\n\n{description or f'A {name} package'}\n")


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
    content = """\"\"\"A custom resource module that provides a simple tool to send \
    GET requests.\"\"\"

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
