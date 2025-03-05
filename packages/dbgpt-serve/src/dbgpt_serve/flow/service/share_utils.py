import io
import json
import os
import tempfile
import zipfile

import aiofiles
import tomlkit
from fastapi import UploadFile

from dbgpt.component import SystemApp
from dbgpt_serve.core import blocking_func_to_async

from ..api.schemas import ServeRequest


def _generate_dbgpts_zip(package_name: str, flow: ServeRequest) -> io.BytesIO:
    zip_buffer = io.BytesIO()
    flow_name = flow.name
    flow_label = flow.label
    flow_description = flow.description
    dag_json = json.dumps(flow.flow_data.dict(), indent=4, ensure_ascii=False)

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # Create MANIFEST.in
        manifest = f"include dbgpts.toml\ninclude {flow_name}/definition/*.json"
        zip_file.writestr(f"{package_name}/MANIFEST.in", manifest)

        # Create README.md
        readme = f"# {flow_label}\n\n{flow_description}"
        zip_file.writestr(f"{package_name}/README.md", readme)

        # Create module __init__.py
        zip_file.writestr(
            f"{package_name}/{flow_name}/__init__.py",
            "",
        )

        # Create flow definition json
        zip_file.writestr(
            f"{package_name}/{flow_name}/definition/flow_definition.json",
            dag_json,
        )

        # Create dbgpts.toml
        dbgpts_toml = tomlkit.document()
        # Add flow information
        dbgpts_flow_toml = tomlkit.document()
        dbgpts_flow_toml.add("label", flow_label)
        name_with_comment = tomlkit.string(flow_name)
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

        # Transform dbgpts.toml to string
        toml_string = tomlkit.dumps(dbgpts_toml)
        zip_file.writestr(f"{package_name}/dbgpts.toml", toml_string)

        # Create pyproject.toml (uv style)
        pyproject_toml = tomlkit.document()

        # Add [project] section (modern PEP 621 format used by uv)
        project_section = tomlkit.table()
        project_section.add("name", package_name)
        project_section.add("version", "0.1.0")
        project_section.add("description", flow_description or "A dbgpts package")
        project_section.add("readme", "README.md")
        project_section.add("requires-python", ">=3.8")
        project_section.add("dependencies", [])
        pyproject_toml["project"] = project_section

        # Add [build-system] section
        build_system = tomlkit.table()
        build_system.add("requires", ["setuptools>=61.0"])
        build_system.add("build-backend", "setuptools.build_meta")
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
