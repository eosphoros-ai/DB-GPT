import json
import logging
import re
from typing import Any, Dict, Optional

from dbgpt.agent import Action, ActionOutput, AgentResource, Resource, ResourceType
from dbgpt.util.json_utils import parse_or_raise_error

from ...resource.tool.base import BaseTool, ToolParameter
from ...resource.tool.pack import ToolPack
from ...util.react_parser import ReActOutputParser, ReActStep
from .tool_action import ToolAction, run_tool

logger = logging.getLogger(__name__)


class Terminate(Action[None], BaseTool):
    """Terminate action.

    It is a special action to terminate the conversation, at same time, it can be a
    tool to return the final answer.
    """

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        return ActionOutput(
            is_exe_success=True,
            terminate=True,
            content=ai_message,
        )

    @classmethod
    def get_action_description(cls) -> str:
        return (
            "Terminate action representing the task is finished, or you think it is"
            " impossible for you to complete the task"
        )

    @classmethod
    def parse_action(
        cls,
        ai_message: str,
        default_action: "Action",
        resource: Optional[Resource] = None,
        **kwargs,
    ) -> Optional["Action"]:
        """Parse the action from the message.

        If you want skip the action, return None.
        """
        if "parser" in kwargs and isinstance(kwargs["parser"], ReActOutputParser):
            parser = kwargs["parser"]
        else:
            parser = ReActOutputParser()
        steps = parser.parse_current_step(ai_message)
        if len(steps) == 0:
            return None
        if len(steps) > 1:
            logger.warning(
                "Terminate.parse_action: Model output contains %d steps, using first.",
                len(steps),
            )
        step: ReActStep = steps[0]
        if not step.action:
            return None
        if step.action.lower() == default_action.name.lower():
            return default_action
        return None

    @property
    def name(self):
        return "terminate"

    @property
    def description(self):
        return self.get_action_description()

    @property
    def args(self):
        return {
            "output": ToolParameter(
                type="string",
                name="output",
                description=(
                    "Final answer to the task, or the reason why you think it "
                    "is impossible to complete the task"
                ),
            ),
        }

    def execute(self, *args, **kwargs):
        if "output" in kwargs:
            return kwargs["output"]
        if "final_answer" in kwargs:
            return kwargs["final_answer"]
        return args[0] if args else "terminate unknown"

    async def async_execute(self, *args, **kwargs):
        return self.execute(*args, **kwargs)


class ReActAction(ToolAction):
    """React action class."""

    def __init__(self, **kwargs):
        """Tool action init."""
        super().__init__(**kwargs)

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return None

    @classmethod
    def parse_action(
        cls,
        ai_message: str,
        default_action: "ReActAction",
        resource: Optional[Resource] = None,
        **kwargs,
    ) -> Optional["ReActAction"]:
        """Parse the action from the message.

        If you want skip the action, return None.
        """
        return default_action

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""

        if "parser" in kwargs and isinstance(kwargs["parser"], ReActOutputParser):
            parser = kwargs["parser"]
        else:
            parser = ReActOutputParser()
        steps = parser.parse_current_step(ai_message)
        if len(steps) == 0:
            raise ValueError("No valid ReAct step found in model output.")
        if len(steps) > 1:
            logger.warning(
                "Model output contains %d steps, only the first will be executed.",
                len(steps),
            )
        step = steps[0]
        act_out = await self._do_run(ai_message, step, need_vis_render=need_vis_render)
        if not act_out.action:
            act_out.action = step.action
        if step.thought:
            act_out.thoughts = step.thought
        if step.phase:
            act_out.phase = step.phase
        if step.action_intention:
            act_out.action_intention = step.action_intention
        if step.action_reason:
            act_out.action_reason = step.action_reason
        if not act_out.action_input and step.action_input:
            if isinstance(step.action_input, str):
                act_out.action_input = step.action_input
            else:
                act_out.action_input = json.dumps(step.action_input, ensure_ascii=False)
        return act_out

    @staticmethod
    def _fallback_parse_args(
        tool_name: str,
        raw_input: Any,
        resource: Optional[Resource],
    ) -> Dict[str, Any]:
        """Infer tool args when JSON parsing fails.

        Strategy:
        1. For single-param tools: regex extract the value, or pass raw input.
        2. For multi-param tools: find each param key position and extract
           the string value between quote delimiters.
        3. Return empty dict as last resort.
        """
        if not resource or not tool_name or not raw_input:
            return {}

        tool_packs = ToolPack.from_resource(resource)
        if not tool_packs:
            return {}
        tool_pack: ToolPack = tool_packs[0]
        try:
            tl = tool_pack._get_execution_tool(tool_name)
        except Exception:
            return {}

        param_names = list(tl.args.keys()) if tl.args else []
        if not param_names:
            return {}

        raw_str = str(raw_input)

        def _unescape(s: str) -> str:
            return (
                s.replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )

        if len(param_names) == 1:
            param_name = param_names[0]
            pattern = re.compile(
                r'["\']?' + re.escape(param_name) + r'["\']?\s*:\s*"(.*)"',
                re.DOTALL,
            )
            m = pattern.search(raw_str)
            if m:
                return {param_name: _unescape(m.group(1))}
            return {param_name: raw_str}

        # Multi-param: locate each "param_name": position in raw text,
        # then extract the quoted value following each key.
        key_positions: list[tuple[str, int]] = []
        for pname in param_names:
            pat = re.compile(
                r'["\']?' + re.escape(pname) + r'["\']?\s*:\s*',
            )
            m = pat.search(raw_str)
            if m:
                val_start = m.end()
                if val_start < len(raw_str) and raw_str[val_start] in ["'", '"']:
                    val_start += 1
                key_positions.append((pname, val_start))

        key_positions.sort(key=lambda x: x[1])

        result: Dict[str, Any] = {}
        for idx, (pname, val_start) in enumerate(key_positions):
            if idx + 1 < len(key_positions):
                next_pname = key_positions[idx + 1][0]
                next_start = key_positions[idx + 1][1]
                # Walk backwards from next key to find the boundary:
                pat_next = re.compile(
                    r'\s*,\s*["\']?' + re.escape(next_pname) + r'["\']?\s*:'
                )
                m_next = pat_next.search(raw_str, val_start)
                if m_next and m_next.start() < next_start:
                    segment = raw_str[val_start : m_next.start()]
                else:
                    segment = raw_str[val_start:next_start]
                    # Find last `",` or `" ,` pattern as value end
                    boundary = segment.rfind(",")
                    if boundary >= 0:
                        segment = segment[:boundary]

                # Strip trailing quotes
                segment = segment.rstrip()
                if segment.endswith('"') or segment.endswith("'"):
                    segment = segment[:-1]

                result[pname] = _unescape(segment)
            else:
                # Last param: take everything up to the last `"` before `}`
                remaining = raw_str[val_start:]
                # Strip trailing `"}` or `" }` etc.
                remaining = remaining.rstrip()
                while (
                    remaining.endswith("}")
                    or remaining.endswith('"')
                    or remaining.endswith("'")
                ):
                    remaining = remaining[:-1]
                    remaining = remaining.rstrip()

                result[pname] = _unescape(remaining)

            # Try to parse the value as JSON if it looks like an object or array
            if isinstance(result[pname], str):
                s_val = result[pname].strip()
                if (s_val.startswith("{") and s_val.endswith("}")) or (
                    s_val.startswith("[") and s_val.endswith("]")
                ):
                    try:
                        result[pname] = json.loads(s_val)
                    except Exception:
                        pass

        if result:
            return result
        return {}

    @staticmethod
    def _extract_html_interpreter_args(raw_input: str) -> Dict[str, Any]:
        """Robust extraction for html_interpreter {"html": ..., "title": ...}.

        HTML content typically contains many double-quotes (class="...",
        style="...") which break standard JSON parsing. This method uses
        a reverse-search strategy:
        1. Find the LAST occurrence of '"title"' followed by ':' (the actual
           JSON key, not an HTML <title> tag).
        2. Extract the title value from after that key.
        3. Everything between the first '"html"' key and the title key is
           the HTML content.
        """
        if not raw_input:
            return {}

        raw = raw_input.strip()

        # Step 1: Find the last occurrence of a title key pattern
        # Pattern: "title" : " (with optional quotes and whitespace)
        title_key_pattern = re.compile(
            r'["\']?title["\']?\s*:\s*["\']',
        )
        # Find ALL matches and use the last one (most likely the actual key)
        title_matches = list(title_key_pattern.finditer(raw))
        if not title_matches:
            # No title key found — treat entire input as html
            html_val_pattern = re.compile(
                r'["\']?html["\']?\s*:\s*["\']',
            )
            m = html_val_pattern.search(raw)
            if m:
                html_start = m.end()
                # Strip trailing "} patterns
                html_content = raw[html_start:]
                html_content = html_content.rstrip()
                while html_content and html_content[-1] in "\"}' ":
                    html_content = html_content[:-1]
                    html_content = html_content.rstrip()
                if html_content:
                    return {"html": html_content, "title": "Report"}
            return {}

        # Use the last title match
        last_title_match = title_matches[-1]
        title_val_start = last_title_match.end()

        # Step 2: Extract title value (short string, ends at quote + } )
        title_content = raw[title_val_start:]
        title_content = title_content.rstrip()
        # Strip trailing }"' characters
        while title_content and title_content[-1] in "\"}' ":
            title_content = title_content[:-1]
            title_content = title_content.rstrip()
        title_value = title_content.strip() or "Report"

        # Step 3: Extract HTML content
        html_val_pattern = re.compile(
            r'["\']?html["\']?\s*:\s*["\']',
        )
        html_m = html_val_pattern.search(raw)
        if not html_m:
            return {}

        html_start = html_m.end()
        # HTML ends just before the title key boundary
        # Walk backwards from title key to find the separator: , "title"
        title_key_start = last_title_match.start()
        html_end = title_key_start

        # Strip trailing separator: comma, whitespace, quotes
        html_content = raw[html_start:html_end]
        html_content = html_content.rstrip()
        if html_content.endswith(","):
            html_content = html_content[:-1].rstrip()
        # Strip trailing quote if present
        if html_content and html_content[-1] in "\"'":
            html_content = html_content[:-1]

        # Unescape common JSON escape sequences
        html_content = (
            html_content.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )

        if html_content:
            html_content = self._repair_truncated_html(html_content)
            return {"html": html_content, "title": title_value}
        return {}

    @staticmethod
    def _repair_truncated_html(html: str) -> str:
        """Auto-close HTML tags that were truncated by LLM token limit.

        Detects unclosed tags and appends closing tags in reverse order.
        Also ensures </body></html> are present if <body>/<html> were opened.
        """
        if not html:
            return html

        # Quick check: if it already looks complete, skip repair
        lower = html.lower()
        if "</html>" in lower and "</body>" in lower:
            return html

        # Track opened tags
        tag_pattern = re.compile(r"<(\w+)(?:\s[^>]*)?>")
        close_tag_pattern = re.compile(r"</(\w+)\s*>")
        self_closing = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}

        open_tags = []
        for m in tag_pattern.finditer(html):
            tag = m.group(1).lower()
            if tag not in self_closing:
                open_tags.append(tag)
        for m in close_tag_pattern.finditer(html):
            tag = m.group(1).lower()
            if tag in open_tags:
                # Remove the last matching open tag
                idx = len(open_tags) - 1 - open_tags[::-1].index(tag)
                open_tags.pop(idx)

        # Append closing tags in reverse order
        if open_tags:
            closing = "".join(f"</{t}>" for t in reversed(open_tags))
            html = html + closing

        return html

    async def _do_run(
        self,
        ai_message: str,
        parsed_step: ReActStep,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        """Perform the action."""
        tool_args = {}
        name = parsed_step.action
        action_input = parsed_step.action_input
        action_input_str = action_input

        # Diagnostic logging for html_interpreter calls
        if name == "html_interpreter":
            input_preview = str(action_input)[:200] if action_input else "<empty>"
            logger.info(
                "html_interpreter called: action_input type=%s, len=%d, preview=%s",
                type(action_input).__name__,
                len(str(action_input)) if action_input else 0,
                input_preview,
            )

        if not name:
            terminal_content = str(action_input_str if action_input_str else ai_message)
            return ActionOutput(
                is_exe_success=True,
                content=terminal_content,
                observations=terminal_content,
                terminate=True,
            )

        try:
            # Try to parse the action input to dict
            if action_input and isinstance(action_input, str):
                tool_args = parse_or_raise_error(action_input)
            elif isinstance(action_input, dict) or isinstance(action_input, list):
                tool_args = action_input
                action_input_str = json.dumps(action_input, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            if parsed_step.action == "terminate":
                tool_args = {"output": action_input}
            elif name == "html_interpreter" and isinstance(action_input, str):
                # Special handling for html_interpreter: the HTML content
                # often contains unescaped quotes that break JSON parsing.
                # Use a robust extraction: find the last "title" key and
                # extract the html content between "html": and the title key.
                tool_args = self._extract_html_interpreter_args(action_input)
                logger.info(
                    "html_interpreter fallback extraction: html=%d chars, title=%s",
                    len(tool_args.get("html", "")) if tool_args else 0,
                    tool_args.get("title") if tool_args else None,
                )
                if not tool_args:
                    tool_args = self._fallback_parse_args(
                        name, action_input, self.resource
                    )
            else:
                # JSON parsing failed — try to infer args from the tool definition.
                # If the tool has exactly one required parameter, treat the raw
                # action_input as that parameter's value.
                tool_args = self._fallback_parse_args(name, action_input, self.resource)
            if not tool_args:
                logger.warning(f"Failed to parse the args: {action_input}")
        # Log resolved args for html_interpreter before execution
        if name == "html_interpreter":
            html_len = (
                len(tool_args.get("html", "")) if isinstance(tool_args, dict) else 0
            )
            fp = tool_args.get("file_path", "") if isinstance(tool_args, dict) else ""
            logger.info(
                "html_interpreter resolved: tool_args keys=%s, "
                "html_len=%d, file_path=%s",
                list(tool_args.keys())
                if isinstance(tool_args, dict)
                else type(tool_args).__name__,
                html_len,
                fp or "<none>",
            )
        act_out = await run_tool(
            name,
            tool_args,
            self.resource,
            self.render_protocol,
            need_vis_render=need_vis_render,
            raw_tool_input=action_input_str,
        )
        if not act_out.action_input:
            act_out.action_input = action_input_str
        return act_out
