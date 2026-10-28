"""The same controlled suite creation tools for DBGPT and PI."""

import json
from pathlib import Path
from typing import Any, Dict

from dbgpt.agent.resource.tool.base import tool
from dbgpt_serve.plugins.creation import CREATION_CAPABILITIES, SuiteCreationStore

CREATOR_READ_TOOLS = {
    "read",
    "read_file",
    "load_file",
    "web_search",
    "web_fetch",
    "sql_query",
    "semantic_get_metadata",
    "semantic_search_business",
    "semantic_search_metrics",
    "semantic_get_metric",
    "kb_ls",
    "kb_glob",
    "kb_grep",
    "kb_cat",
    "kb_semantic",
    "get_skill_resource",
    "load_skill",
    "question",
    "todowrite",
    "terminate",
}


def creation_tool_allowed(name: str) -> bool:
    return name in CREATOR_READ_TOOLS or name in {
        "suite_draft_create",
        "suite_draft_read",
        "suite_draft_write",
        "suite_draft_validate",
        "suite_package_build",
    }


def creator_instructions() -> str:
    return (Path(__file__).parent / "suite_creator" / "SKILL.md").read_text("utf-8")


def creator_read_step() -> Dict[str, Any]:
    from ..skill_read_steps import _read_step

    return _read_step(
        "skill-read-suite-creator",
        "expert-suite-creator",
        [
            {
                "path": str(Path(__file__).parent / "suite_creator" / "SKILL.md"),
                "content": creator_instructions(),
            }
        ],
        "专家套件创建",
    )


def make_suite_creation_tools(conv_id: str):
    store = SuiteCreationStore()

    def result(fn, *args):
        try:
            return json.dumps({"success": True, "data": fn(*args)}, ensure_ascii=False)
        except (ValueError, TypeError) as exc:
            return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)

    @tool(
        description="创建专家套件隔离草稿，返回 draft_id 和 revision。"
        "参数 requirement 为目标、材料和技能需求。"
    )
    def suite_draft_create(requirement: str) -> str:
        return result(store.create, requirement, conv_id)

    @tool(description="读取套件草稿全部文件和当前 revision。参数 draft_id。")
    def suite_draft_read(draft_id: str) -> str:
        return result(store.read, draft_id)

    @tool(
        description="写入或修改套件文本文件。files_json 是 JSON 对象字符串："
        "相对路径映射完整正文。expected_revision 为当前修订号。"
        "只接受 Markdown/JSON；禁止脚本和凭证。"
    )
    def suite_draft_write(
        draft_id: str, expected_revision: int, files_json: str
    ) -> str:
        try:
            files = json.loads(files_json)
            if not isinstance(files, dict):
                raise ValueError("files_json must be an object")
        except ValueError as exc:
            return json.dumps({"success": False, "error": str(exc)})
        return result(store.write, draft_id, files, expected_revision)

    @tool(
        description="严格校验套件指定修订的结构、技能、引用、工具依赖、输出契约。"
        "修复 errors 后重试。支持的平台工具："
        + ", ".join(sorted(CREATION_CAPABILITIES))
    )
    def suite_draft_validate(draft_id: str, expected_revision: int) -> str:
        return result(store.validate, draft_id, expected_revision)

    @tool(
        description="冻结校验通过的修订，生成专家套件产物卡片，供用户预览编辑下载和一键安装。不会自动安装。"
    )
    def suite_package_build(draft_id: str, expected_revision: int) -> str:
        try:
            artifact = store.build(draft_id, expected_revision)
            # Files remain available through the artifact API. Keep model
            # context small while persisting a stable artifact reference.
            payload = {k: v for k, v in artifact.items() if k != "files"}
            return json.dumps(
                {
                    "success": True,
                    "artifact_id": artifact["artifact_id"],
                    "chunks": [{"output_type": "expert_suite", "content": payload}],
                },
                ensure_ascii=False,
            )
        except ValueError as exc:
            return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)

    return [
        suite_draft_create,
        suite_draft_read,
        suite_draft_write,
        suite_draft_validate,
        suite_package_build,
    ]
