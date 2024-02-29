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
        raise click.ClickException(
            f"Unsupported definition type: {definition_type} for dbgpts type: {dbgpts_type}"
        )


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
