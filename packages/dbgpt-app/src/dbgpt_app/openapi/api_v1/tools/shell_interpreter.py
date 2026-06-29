"""shell_interpreter tool — run bash commands in a sandboxed environment."""

import json
import logging
import os
import uuid
from typing import Any, Dict, List

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)


def make_shell_interpreter(react_state: Dict[str, Any]):
    @tool(
        description=(
            "Execute shell/bash commands in a sandboxed environment. "
            "Use this tool when you need to run shell commands such as ls, cat, "
            "grep, curl, apt, pip, git, or any other CLI tool. "
            "The sandbox provides resource limits (256MB memory, 30s timeout) "
            "and process isolation. "
            'Parameters: {"code": "shell command(s) to execute"}'
        )
    )
    async def shell_interpreter(code: str) -> str:
        """Execute shell/bash commands in a sandboxed environment."""
        if not code or not code.strip():
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No command provided"}]},
                ensure_ascii=False,
            )

        try:
            from dbgpt_sandbox.sandbox.execution_layer.base import (
                ExecutionStatus,
                SessionConfig,
            )
            from dbgpt_sandbox.sandbox.execution_layer.local_runtime import LocalRuntime
        except ImportError:
            return json.dumps(
                {
                    "chunks": [
                        {"output_type": "code", "content": code.strip()},
                        {
                            "output_type": "text",
                            "content": (
                                "Error: dbgpt-sandbox package is not installed. "
                                "Please install it with: pip install dbgpt-sandbox"
                            ),
                        },
                    ]
                },
                ensure_ascii=False,
            )

        from dbgpt.configs.model_config import ROOT_PATH

        session_id = f"bash_{uuid.uuid4().hex[:12]}"
        runtime = LocalRuntime()
        sandbox_work_dir = ROOT_PATH
        os.makedirs(sandbox_work_dir, exist_ok=True)

        config = SessionConfig(
            language="bash",
            working_dir=sandbox_work_dir,
            max_memory=256 * 1024 * 1024,  # 256MB
            timeout=30,
        )

        output_text = ""
        try:
            session = await runtime.create_session(session_id, config)
            result = await session.execute(code)

            if result.status == ExecutionStatus.SUCCESS:
                output_text = result.output or ""
            elif result.status == ExecutionStatus.TIMEOUT:
                output_text = f"Execution timed out ({config.timeout}s limit)"
            else:
                output_text = result.error or "Unknown execution error"
                if result.output:
                    output_text = result.output + "\n[ERROR]\n" + output_text
        except Exception as e:
            output_text = f"Sandbox execution error: {e}"
        finally:
            try:
                await runtime.destroy_session(session_id)
            except Exception:
                pass

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            chunks.append({"output_type": "text", "content": output_text.strip()})
        else:
            chunks.append({"output_type": "text", "content": "(no output)"})

        # Safety-net post-processing for skill script execution
        _code_lower = code.strip().lower()
        _is_skill_script = "skills/" in _code_lower and ".py" in _code_lower
        if _is_skill_script and output_text.strip():
            import shutil

            from dbgpt.configs.model_config import PILOT_PATH, STATIC_MESSAGE_IMG_PATH

            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

            if "calculate_ratios" in _code_lower:
                try:
                    ratio_data = json.loads(output_text.strip())
                    if isinstance(ratio_data, dict):
                        react_state["ratio_data"] = ratio_data
                except Exception:
                    pass

            if "generate_charts" in _code_lower:
                try:
                    os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                    try:
                        chart_output = json.loads(output_text.strip())
                        if isinstance(chart_output, dict):
                            chart_map = chart_output.get("charts", chart_output)
                            for name, abs_path in chart_map.items():
                                if isinstance(abs_path, str) and os.path.isfile(
                                    abs_path
                                ):
                                    ext = os.path.splitext(abs_path)[1].lower()
                                    if ext in IMAGE_EXTS:
                                        basename = os.path.basename(abs_path)
                                        unique_name = (
                                            f"{uuid.uuid4().hex[:8]}_{basename}"
                                        )
                                        dest = os.path.join(
                                            STATIC_MESSAGE_IMG_PATH, unique_name
                                        )
                                        shutil.copy2(abs_path, dest)
                                        img_url = f"/images/{unique_name}"
                                        react_state.setdefault(
                                            "generated_images", []
                                        ).append(img_url)
                                        orig_stem = os.path.splitext(
                                            os.path.basename(abs_path)
                                        )[0].lower()
                                        react_state.setdefault("image_url_map", {})[
                                            orig_stem
                                        ] = img_url
                    except (json.JSONDecodeError, TypeError):
                        pass

                    cid = react_state.get("conv_id") or "default"
                    out_dir = os.path.join(PILOT_PATH, "tmp", cid)
                    if os.path.isdir(out_dir):
                        for fname in os.listdir(out_dir):
                            ext = os.path.splitext(fname)[1].lower()
                            if ext in IMAGE_EXTS:
                                abs_path = os.path.join(out_dir, fname)
                                orig_stem = os.path.splitext(fname)[0].lower()
                                if orig_stem not in react_state.get(
                                    "image_url_map", {}
                                ):
                                    unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                                    dest = os.path.join(
                                        STATIC_MESSAGE_IMG_PATH, unique_name
                                    )
                                    shutil.copy2(abs_path, dest)
                                    img_url = f"/images/{unique_name}"
                                    react_state.setdefault(
                                        "generated_images", []
                                    ).append(img_url)
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
                except Exception as e:
                    logger.warning(
                        "shell_interpreter: image post-processing failed: %s", e
                    )

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return shell_interpreter
