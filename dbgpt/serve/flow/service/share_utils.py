import io
import json
import os
import tempfile
import zipfile

import aiofiles
import tomlkit
from fastapi import UploadFile

from dbgpt.component import SystemApp
from dbgpt.serve.core import blocking_func_to_async

from ..api.schemas import ServeRequest


def _generate_dbgpts_zip(package_name: str, flow: ServeRequest) -> io.BytesIO:

    zip_buffer = io.BytesIO()
    flow_name = flow.name
    flow_label = flow.label
    flow_description = flow.description
    dag_json = json.dumps(flow.flow_data.dict(), indent=4, ensure_ascii=False)
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        manifest = f"include dbgpts.toml\ninclude {flow_name}/definition/*.json"
        readme = f"# {flow_label}\n\n{flow_description}"
        zip_file.writestr(f"{package_name}/MANIFEST.in", manifest)
        zip_file.writestr(f"{package_name}/README.md", readme)
        zip_file.writestr(
            f"{package_name}/{flow_name}/__init__.py",
            "",
        )
        zip_file.writestr(
            f"{package_name}/{flow_name}/definition/flow_definition.json",
            dag_json,
        )
        dbgpts_toml = tomlkit.document()
        # Add flow information
        dbgpts_flow_toml = tomlkit.document()
        dbgpts_flow_toml.add("label", "Simple Streaming Chat")
        name_with_comment = tomlkit.string("awel_flow_simple_streaming_chat")
        name_with_comment.comment("A unique name for all dbgpts")
        dbgpts_flow_toml.add("name", name_with_comment)

        dbgpts_flow_toml.add("version", "0.1.0")
        dbgpts_flow_toml.add(
            "description",
            flow_description,
        )
        dbgpts_flow_toml.add("authors", [])

        definition_type_with_comment = tomlkit.string("json")
        definition_type_with_comment.comment("How to define the flow, python or json")
        dbgpts_flow_toml.add("definition_type", definition_type_with_comment)

        dbgpts_toml.add("flow", dbgpts_flow_toml)

        # Add python and json config
        python_config = tomlkit.table()
        dbgpts_toml.add("python_config", python_config)

        json_config = tomlkit.table()
        json_config.add("file_path", "definition/flow_definition.json")
        json_config.comment("Json config")

        dbgpts_toml.add("json_config", json_config)

        # Transform to string
        toml_string = tomlkit.dumps(dbgpts_toml)
        zip_file.writestr(f"{package_name}/dbgpts.toml", toml_string)

        pyproject_toml = tomlkit.document()

        # Add [tool.poetry] section
        tool_poetry_toml = tomlkit.table()
        tool_poetry_toml.add("name", package_name)
        tool_poetry_toml.add("version", "0.1.0")
        tool_poetry_toml.add("description", "A dbgpts package")
        tool_poetry_toml.add("authors", [])
        tool_poetry_toml.add("readme", "README.md")
        pyproject_toml["tool"] = tomlkit.table()
        pyproject_toml["tool"]["poetry"] = tool_poetry_toml

        # Add [tool.poetry.dependencies] section
        dependencies = tomlkit.table()
        dependencies.add("python", "^3.10")
        pyproject_toml["tool"]["poetry"]["dependencies"] = dependencies

        # Add [build-system] section
        build_system = tomlkit.table()
        build_system.add("requires", ["poetry-core"])
        build_system.add("build-backend", "poetry.core.masonry.api")
        pyproject_toml["build-system"] = build_system

        # Transform to string
        pyproject_toml_string = tomlkit.dumps(pyproject_toml)
        zip_file.writestr(f"{package_name}/pyproject.toml", pyproject_toml_string)
    zip_buffer.seek(0)
    return zip_buffer


async def _parse_flow_from_zip_file(
    file: UploadFile, sys_app: SystemApp
) -> ServeRequest:
    from dbgpt.util.dbgpts.loader import _load_flow_package_from_zip_path

    filename = file.filename
    if not filename.endswith(".zip"):
        raise ValueError("Uploaded file must be a ZIP file")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, filename)

        # Save uploaded file to temporary directory
        async with aiofiles.open(zip_path, "wb") as out_file:
            while content := await file.read(1024 * 64):  # Read in chunks of 64KB
                await out_file.write(content)
        flow = await blocking_func_to_async(
            sys_app, _load_flow_package_from_zip_path, zip_path
        )
        return flow
