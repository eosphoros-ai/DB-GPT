"""code_interpreter tool — execute Python code in a subprocess."""

import asyncio
import json
import logging
import os
import shutil
import sys
import uuid
from typing import Any, Dict, List, Optional

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)


def _try_repair_truncated_code(raw_code: str) -> Optional[str]:
    """Attempt to fix code that was truncated by the LLM's token limit."""
    lines = raw_code.split("\n")
    for trim in range(1, min(11, len(lines))):
        candidate_lines = lines[: len(lines) - trim]
        if not candidate_lines:
            continue
        candidate = "\n".join(candidate_lines)
        open_chars = {"(": ")", "[": "]", "{": "}"}
        close_chars = set(open_chars.values())
        stack: list = []
        for ch in candidate:
            if ch in open_chars:
                stack.append(open_chars[ch])
            elif ch in close_chars:
                if stack and stack[-1] == ch:
                    stack.pop()
        if stack:
            candidate += "\n" + "".join(reversed(stack))
        try:
            compile(candidate, "<repair>", "exec")
            return candidate
        except SyntaxError:
            continue
    return None


def make_code_interpreter(react_state: Dict[str, Any]):
    @tool(
        description=(
            "Execute Python code for data analysis and computation. "
            "Supports pandas, numpy, matplotlib, json, os, etc. "
            "Use this tool when you need to run Python code to process data, "
            "generate charts, or perform calculations. "
            'Parameters: {{"code": "python code string"}}'
        )
    )
    async def code_interpreter(code: str) -> str:
        """Execute arbitrary Python code and return stdout/stderr.

        CRITICAL: Each call is completely independent — variables do NOT
        persist between calls. Every code snippet MUST include all necessary
        data loading and processing. Always print() results you want to see.
        """
        from dbgpt.configs.model_config import PILOT_PATH, STATIC_MESSAGE_IMG_PATH

        if not code or not code.strip():
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No code provided"}]},
                ensure_ascii=False,
            )

        cid = react_state.get("conv_id") or "default"
        work_dir = os.path.join(PILOT_PATH, "tmp", cid)
        os.makedirs(work_dir, exist_ok=True)

        IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        pre_existing_images: set = set()
        for root, _dirs, files in os.walk(work_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTS:
                    pre_existing_images.add(os.path.join(root, f))

        preamble_lines = [
            "import json",
            "import os",
            "import pandas as pd",
            "import numpy as np",
            f'PLOT_DIR = r"{work_dir}"',
            "os.makedirs(PLOT_DIR, exist_ok=True)",
        ]
        fp = react_state.get("file_path")
        if fp:
            preamble_lines.append(f'FILE_PATH = r"{fp}"')
        preamble = "\n".join(preamble_lines) + "\n"
        full_code = preamble + code

        try:
            compile(full_code, "<code_interpreter>", "exec")
        except SyntaxError as se:
            repaired = _try_repair_truncated_code(full_code)
            if repaired is not None:
                logger.warning(
                    "code_interpreter: auto-repaired truncated code "
                    "(original SyntaxError: %s line %s)",
                    se.msg,
                    se.lineno,
                )
                full_code = repaired
                code = full_code[len(preamble) :]
            else:
                error_msg = (
                    f"SyntaxError before execution: {se.msg} "
                    f"(line {se.lineno})\n"
                    "Please regenerate complete, syntactically valid Python code. "
                    "Keep code under 80 lines."
                )
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "code", "content": code.strip()},
                            {"output_type": "text", "content": error_msg},
                        ]
                    },
                    ensure_ascii=False,
                )

        output_text = ""
        try:
            tmp_path = os.path.join(work_dir, "_run.py")
            with open(tmp_path, "w") as tmp:
                tmp.write(full_code)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            output_text = stdout.decode("utf-8", errors="replace")
            error_text = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and error_text:
                output_text = (
                    output_text + "\n[ERROR]\n" + error_text
                    if output_text
                    else error_text
                )
        except asyncio.TimeoutError:
            output_text = "Execution timed out (60s limit)"
        except Exception as e:
            output_text = f"Execution error: {e}"

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            clean_output = output_text.strip()
            max_out_len = 2000
            if len(clean_output) > max_out_len:
                truncation_notice = (
                    f"\n\n... [Output truncated, length: {len(clean_output)} chars."
                    f" Only showing first {max_out_len} chars.]"
                )
                clean_output = clean_output[:max_out_len] + truncation_notice
            chunks.append({"output_type": "text", "content": clean_output})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output — add print() to see results)",
                }
            )

        # Scan for new images generated by this run
        try:
            os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    full_path = os.path.join(root, fname)
                    if ext in IMAGE_EXTS and full_path not in pre_existing_images:
                        unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                        dest = os.path.join(STATIC_MESSAGE_IMG_PATH, unique_name)
                        shutil.copy2(full_path, dest)
                        img_url = f"/images/{unique_name}"
                        chunks.append({"output_type": "image", "content": img_url})
                        react_state.setdefault("generated_images", []).append(img_url)
        except Exception:
            pass

        # Clean up temp script
        try:
            script_path = os.path.join(work_dir, "_run.py")
            if os.path.exists(script_path):
                os.remove(script_path)
        except Exception:
            pass

        all_images = react_state.get("generated_images", [])
        if all_images:
            img_summary = "已生成的图片URL（在生成HTML时请使用这些URL）:\n" + "\n".join(
                f"  - {url}" for url in all_images
            )
            chunks.append({"output_type": "text", "content": img_summary})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return code_interpreter
