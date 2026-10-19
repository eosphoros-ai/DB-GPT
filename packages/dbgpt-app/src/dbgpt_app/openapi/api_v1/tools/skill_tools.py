"""load_skill tool — loads skill content (SKILL.md) by name."""

import json
import time
from typing import Any, Dict

from dbgpt.agent.resource.tool.base import tool


def _authorized_skill_input_paths(react_state: Dict[str, Any]) -> list[str]:
    """Use server-materialized attachments, not paths supplied in tool args."""
    manifests = react_state.get("session_files") or []
    if not manifests:
        # Legacy uploads are validated by agentic_data_api before entering
        # react_state. This value is not a model-facing tool parameter.
        path = react_state.get("file_path")
        return [path] if isinstance(path, str) and path else []
    paths = react_state.get("session_file_paths") or {}
    allowed = []
    for manifest in manifests:
        file_id = (
            manifest.get("file_id")
            if isinstance(manifest, dict)
            else getattr(manifest, "file_id", None)
        )
        status = (
            manifest.get("status")
            if isinstance(manifest, dict)
            else getattr(manifest, "status", None)
        )
        if getattr(status, "value", status) != "ready":
            continue
        path = paths.get(file_id)
        if isinstance(path, str) and path:
            allowed.append(path)
    return allowed


def make_load_skill(react_state: Dict[str, Any]):
    """Return a ``load_skill`` FunctionTool bound to the given react_state."""

    @tool(
        description="Load skill content by skill name and file path. "
        "Returns the SKILL.md content of the specified skill. "
        '参数: {"skill_name": "技能名称", "file_path": "技能文件路径"}'
    )
    def load_skill(skill_name: str, file_path: str) -> str:
        """Load the skill content (SKILL.md) by skill name and file path."""
        from dbgpt.agent.claude_skill import get_registry

        registry = get_registry()
        matched = registry.get_skill(skill_name)

        if not matched:
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    matched = registry.get_skill(s.name)
                    break

        if not matched:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Skill '{skill_name}' not found",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        react_state["matched"] = matched
        react_state["skill_prompt"] = matched.get_prompt()

        chunks = [
            {"output_type": "text", "content": f"Skill: {matched.metadata.name}"},
            {"output_type": "text", "content": f"File path: {file_path}"},
            {"output_type": "text", "content": "---"},
        ]

        if matched.instructions:
            chunks.append({"output_type": "markdown", "content": matched.instructions})
        elif matched.prompt_template:
            prompt_text = (
                matched.prompt_template.template
                if hasattr(matched.prompt_template, "template")
                else str(matched.prompt_template)
            )
            chunks.append({"output_type": "markdown", "content": prompt_text})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return load_skill


def make_execute_skill_script_file(react_state: Dict[str, Any]):
    """Return an ``execute_skill_script_file`` FunctionTool bound to react_state."""

    @tool(
        description="执行技能scripts目录下的脚本文件。参数: "
        '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}。'
        "JSON 脚本用 args；命令行脚本用 argv 字符串列表，二者不能同时提供。"
        '例如 init_skill.py 用 argv=["sql-data-analysis", "--path", '
        '"技能目录的绝对路径"]。'
        "返回真实 artifact_id。复用上一步结果时，用 input_artifact_ids 标明输入产物。"
    )
    async def execute_skill_script_file(
        skill_name: str,
        script_file_name: str,
        args: dict | None = None,
        input_artifact_ids: list[str] | None = None,
        argv: list[str] | None = None,
    ) -> str:
        """Execute a script file from a skill's scripts directory."""
        import os
        import uuid

        from dbgpt._private.config import Config
        from dbgpt.agent.skill.manage import get_skill_manager
        from dbgpt.configs.model_config import PILOT_PATH
        from dbgpt.core.interface.report_capture import (
            capture_python_execution,
            execution_output_files,
            publish_generated_images,
            resolve_argument_dependencies,
            snapshot_execution_files,
        )
        from dbgpt_app.openapi.api_v1.tools._helpers import (
            _extract_auto_data_markers,
        )

        CFG = Config()

        try:
            if args and argv is not None:
                raise ValueError("Use either args (JSON) or argv (CLI), not both")
            sink = react_state.get("_report_artifact_sink")
            available = (
                {a.artifact_id for a in sink.snapshot() if a.status == "succeeded"}
                if sink
                else set()
            )
            if set(input_artifact_ids or []) - available:
                raise ValueError("Unknown or unsuccessful input_artifact_ids")
            sm = get_skill_manager(CFG.SYSTEM_APP)
            cid = react_state.get("conv_id") or "default"
            out_dir = os.path.join(
                PILOT_PATH, "tmp", cid, "executions", uuid.uuid4().hex
            )
            os.makedirs(out_dir, exist_ok=True)

            real_file_path = react_state.get("file_path")
            if real_file_path and args:
                _FILE_PATH_KEYS = {
                    "input_file",
                    "file_path",
                    "data_path",
                    "csv_path",
                    "excel_path",
                    "data_file",
                }
                for key in list(args.keys()):
                    if key in _FILE_PATH_KEYS:
                        args[key] = real_file_path

            execution_args = {"argv": argv} if argv is not None else (args or {})
            input_artifact_ids = resolve_argument_dependencies(
                execution_args, sink, input_artifact_ids or []
            )
            execution_args, file_input_ids = snapshot_execution_files(
                execution_args,
                sink,
                action="execute_skill_script_file.input",
                allowed_paths=_authorized_skill_input_paths(react_state),
            )
            input_artifact_ids = list(
                dict.fromkeys([*(input_artifact_ids or []), *file_input_ids])
            )
            started_at = time.perf_counter()
            cli_kwargs = {"argv": execution_args["argv"]} if argv is not None else {}
            result_str = await sm.execute_skill_script_file(
                skill_name,
                script_file_name,
                {} if argv is not None else execution_args,
                output_dir=out_dir,
                **cli_kwargs,
            )

            try:
                result_obj = json.loads(result_str)
                chunks = result_obj.get("chunks", [])
                _script_source = result_obj.get("source_code")
                script_result = None
                for chunk in chunks:
                    if chunk.get("output_type") in {"text", "json"}:
                        try:
                            content = chunk.get("content")
                            parsed = (
                                json.loads(content)
                                if isinstance(content, str)
                                else content
                            )
                            if isinstance(parsed, (dict, list)):
                                script_result = parsed
                        except (ValueError, TypeError):
                            pass
                if _script_source:
                    chunks.insert(0, {"output_type": "code", "content": _script_source})

                captured_images = publish_generated_images(
                    [
                        chunk["content"]
                        for chunk in chunks
                        if chunk.get("output_type") == "image"
                        and os.path.isfile(chunk.get("content", ""))
                    ]
                )
                published = {image["source_path"]: image for image in captured_images}
                for chunk in chunks:
                    image = published.get(str(chunk.get("content")))
                    if chunk.get("output_type") == "image" and image:
                        chunk["content"] = image["uri"]
                for image in captured_images:
                    react_state.setdefault("generated_images", []).append(image["uri"])
                    react_state.setdefault("image_url_map", {})[
                        os.path.splitext(image["filename"])[0].lower()
                    ] = image["uri"]

                all_images = react_state.get("generated_images", [])
                if all_images:
                    img_summary = (
                        "已生成的图片URL（在生成HTML报告时请使用这些URL）:\n"
                        + "\n".join(f"  - {url}" for url in all_images)
                    )
                    chunks.append({"output_type": "text", "content": img_summary})

                auto_data = react_state.get("auto_data")
                if not isinstance(auto_data, dict):
                    auto_data = {}
                    react_state["auto_data"] = auto_data

                filtered_chunks = []
                script_template_data = {}
                for chunk in chunks:
                    if chunk.get("output_type") != "text":
                        filtered_chunks.append(chunk)
                        continue
                    content = chunk.get("content") or ""
                    cleaned, extracted = _extract_auto_data_markers(content)
                    if extracted:
                        auto_data.update(extracted)
                        script_template_data.update(extracted)
                    if cleaned:
                        chunk["content"] = cleaned
                        filtered_chunks.append(chunk)
                    elif not extracted:
                        filtered_chunks.append(chunk)
                chunks = filtered_chunks
                if script_template_data:
                    script_result = {
                        **(script_result if isinstance(script_result, dict) else {}),
                        **script_template_data,
                    }
                script_error = result_obj.get("error") or (
                    script_result.get("error")
                    if isinstance(script_result, dict)
                    else None
                )
                if result_obj.get("success") is False and not script_error:
                    script_error = "Skill script execution failed"

                # Skill scripts are a real Python execution boundary just like
                # code_interpreter.  Capturing them here keeps reports generated
                # from CSV/PDF/financial skills inside the same evidence contract
                # as database analysis, instead of producing an untraceable
                # legacy Report.html.
                text_output = "\n".join(
                    str(chunk.get("content") or "")
                    for chunk in chunks
                    if chunk.get("output_type") in {"text", "markdown", "json"}
                )
                python_artifact_id = capture_python_execution(
                    code=_script_source
                    or f"# Skill script: {skill_name}/{script_file_name}",
                    duration_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
                    status=result_obj.get("status", "failed")
                    if script_error
                    else "succeeded",
                    exit_code=result_obj.get("exit_code", None if script_error else 0),
                    stdout=text_output,
                    stderr=result_obj.get("stderr", ""),
                    error=str(script_error) if script_error else None,
                    result_inline=script_result,
                    input_artifact_ids=input_artifact_ids,
                    images=captured_images,
                    output_files=execution_output_files(out_dir),
                    action="execute_skill_script_file",
                    metadata={
                        "capability_type": "skill",
                        "skill_name": skill_name,
                        "script_file_name": script_file_name,
                        "arguments": result_obj.get("script_arguments", args),
                    },
                    artifact_sink=react_state.get("_report_artifact_sink"),
                )
                if not script_error and isinstance(script_result, dict):
                    for key, value in script_result.items():
                        if (
                            isinstance(key, str)
                            and key.isupper()
                            and isinstance(value, (str, int, float))
                            and not isinstance(value, bool)
                        ):
                            auto_data[key] = value

                return json.dumps(
                    {
                        "chunks": chunks,
                        "artifact_id": python_artifact_id,
                        **(
                            {"success": False, "error_code": "SKILL_SCRIPT_FAILED"}
                            if script_error
                            else {}
                        ),
                    },
                    ensure_ascii=False,
                )
            except (json.JSONDecodeError, KeyError):
                return result_str
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}],
                    "success": False,
                    "error_code": "SKILL_SCRIPT_FAILED",
                },
                ensure_ascii=False,
            )

    return execute_skill_script_file
