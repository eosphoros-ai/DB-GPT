"""load_skill tool — loads skill content (SKILL.md) by name."""

import json
from typing import Any, Dict

from dbgpt.agent.resource.tool.base import tool


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
        '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
    )
    async def execute_skill_script_file(
        skill_name: str, script_file_name: str, args: dict | None = None
    ) -> str:
        """Execute a script file from a skill's scripts directory."""
        import os
        import shutil
        import uuid

        from dbgpt._private.config import Config
        from dbgpt.agent.skill.manage import get_skill_manager
        from dbgpt.configs.model_config import PILOT_PATH, STATIC_MESSAGE_IMG_PATH
        from dbgpt_app.openapi.api_v1.tools._helpers import (
            _extract_auto_data_markers,
        )

        CFG = Config()

        try:
            sm = get_skill_manager(CFG.SYSTEM_APP)
            cid = react_state.get("conv_id") or "default"
            out_dir = os.path.join(PILOT_PATH, "tmp", cid)
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

            result_str = await sm.execute_skill_script_file(
                skill_name,
                script_file_name,
                args or {},
                output_dir=out_dir,
            )

            try:
                _skill_path = sm._get_skill_path(skill_name)
                _sf = script_file_name.lstrip("/\\")
                if _sf.startswith("scripts/") or _sf.startswith("scripts\\"):
                    _sf = _sf[8:]
                _script_abs = os.path.join(_skill_path, "scripts", _sf)
                with open(_script_abs, "r", encoding="utf-8") as _f:
                    _script_source = _f.read()
            except Exception:
                _script_source = None

            try:
                result_obj = json.loads(result_str)
                chunks = result_obj.get("chunks", [])
                if _script_source:
                    chunks.insert(0, {"output_type": "code", "content": _script_source})

                IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                for chunk in chunks:
                    if chunk.get("output_type") == "image":
                        abs_path = chunk["content"]
                        if os.path.isabs(abs_path) and os.path.isfile(abs_path):
                            ext = os.path.splitext(abs_path)[1].lower()
                            if ext in IMAGE_EXTS:
                                unique_name = (
                                    f"{uuid.uuid4().hex[:8]}_"
                                    f"{os.path.basename(abs_path)}"
                                )
                                dest = os.path.join(
                                    STATIC_MESSAGE_IMG_PATH, unique_name
                                )
                                shutil.copy2(abs_path, dest)
                                img_url = f"/images/{unique_name}"
                                chunk["content"] = img_url
                                react_state.setdefault("generated_images", []).append(
                                    img_url
                                )
                                orig_stem = os.path.splitext(
                                    os.path.basename(abs_path)
                                )[0].lower()
                                react_state.setdefault("image_url_map", {})[
                                    orig_stem
                                ] = img_url

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
                for chunk in chunks:
                    if chunk.get("output_type") != "text":
                        filtered_chunks.append(chunk)
                        continue
                    content = chunk.get("content") or ""
                    cleaned, extracted = _extract_auto_data_markers(content)
                    if extracted:
                        auto_data.update(extracted)
                    if cleaned:
                        chunk["content"] = cleaned
                        filtered_chunks.append(chunk)
                    elif not extracted:
                        filtered_chunks.append(chunk)
                chunks = filtered_chunks

                if script_file_name == "calculate_ratios.py":
                    for chunk in chunks:
                        if chunk.get("output_type") == "text":
                            try:
                                ratio_data = json.loads(chunk["content"])
                                react_state["ratio_data"] = ratio_data
                            except Exception:
                                pass

                return json.dumps({"chunks": chunks}, ensure_ascii=False)
            except (json.JSONDecodeError, KeyError):
                return result_str
        except Exception as e:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
                ensure_ascii=False,
            )

    return execute_skill_script_file
