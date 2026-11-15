"""Render the conversational agent's tool inventory from its bound resources."""

import json
import re

from dbgpt.core import PromptTemplate

from .tools.financial_tools import FINANCIAL_AGENT_PROMPT

REGISTERED_TOOLS_PROMPT = """
## Available Tools Description
The following tools are registered for this turn. Use their exact names and
parameter schemas.
{% if native_function_calling %}
Invoke the supplied native functions with complete JSON arguments.
Do not emit a bare `Action:` line or describe an intended call instead of calling it.
{% else %}
Invoke them directly with `Action: <tool_name>` and JSON
`Action Input`; do not treat a tool name as a skill script or wrap it in
execute_skill_script, execute_skill_script_file, or execute_tool.
{% endif %}
Only use a skill script executor for a script explicitly provided by that skill.
Tools absent from this list are unavailable; do not invent tools or script names.

{% if not native_function_calling %}
{{ action_space }}
{% endif %}

Action must be one of: [{{ action_space_names }}].
{% if native_function_calling %}
When finished, call the registered terminate function with {"output": "final answer"}.
{% else %}
Every response must contain exactly one Action and one Action Input.
When finished, return the user-facing answer through the registered terminate tool:
Action: terminate
Action Input: {"output": "final answer"}
Put only the final answer in output; do not include Thought or Action prefixes.
{% endif %}
"""


def build_react_prompt_template(
    workflow_prompt: str, *, financial_enabled: bool
) -> PromptTemplate:
    """Keep custom prompts aligned with ReActAgent's actual action space.

    ReActAgent populates action_space from the bound ToolPack for each reply.
    A custom template must include it rather than replace it with a static list.
    Rendering descriptions as variables also preserves literal JSON/references.
    """
    # Historical workflow prose duplicated the authoritative action-space
    # schema. Keep task/skill/context sections, discard only the inventory.
    workflow_prompt = re.sub(
        r"^## Available Tools Description\n.*?(?=^## |\Z)",
        "",
        workflow_prompt,
        flags=re.MULTILINE | re.DOTALL,
    )
    workflow_prompt = workflow_prompt.replace(
        "execute_skill_script_file", "run_skill_script"
    )
    sections = [workflow_prompt]
    sections.append(
        "Use only supplied functions. If a needed capability is absent and "
        "tool_search is available, discover it before calling it. Discovery "
        "is limited to this turn's authorized catalog.\n"
        "For Python report analysis, assign computed metrics/tables to "
        "REPORT_RESULT as JSON-compatible values; printed text is not a "
        "data binding. Link only completed, captured artifacts."
    )
    if financial_enabled:
        sections.append(FINANCIAL_AGENT_PROMPT)
    # The workflow already contains rendered package instructions and source
    # text. Insert it as a quoted Jinja string value so literal placeholders,
    # JSON, and even template delimiters are never evaluated a second time.
    literal_instructions = json.dumps("\n\n".join(sections), ensure_ascii=False)
    return PromptTemplate(
        template="{{ " + literal_instructions + " }}\n\n" + REGISTERED_TOOLS_PROMPT,
        input_variables=[
            "action_space",
            "action_space_names",
            "native_function_calling",
        ],
        template_format="jinja2",
    )
