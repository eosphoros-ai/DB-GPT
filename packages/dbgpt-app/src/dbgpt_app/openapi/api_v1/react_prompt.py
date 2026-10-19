"""Render the conversational agent's tool inventory from its bound resources."""

from dbgpt.core import PromptTemplate

from .tools.financial_tools import FINANCIAL_AGENT_PROMPT

REGISTERED_TOOLS_PROMPT = """
## Available Tools Description
The following tools are registered for this turn. Use their exact names and
parameter schemas. Invoke them directly with `Action: <tool_name>` and JSON
`Action Input`; do not treat a tool name as a skill script or wrap it in
execute_skill_script, execute_skill_script_file, or execute_tool.
Only use a skill script executor for a script explicitly provided by that skill.
Tools absent from this list are unavailable; do not invent tools or script names.

{{ action_space }}

Action must be one of: [{{ action_space_names }}].
Every response must contain exactly one Action and one Action Input.
When finished, return the user-facing answer through the registered terminate tool:
Action: terminate
Action Input: {"output": "final answer"}
Put only the final answer in output; do not include Thought or Action prefixes.
"""


def build_react_prompt_template(
    workflow_prompt: str, *, financial_enabled: bool
) -> PromptTemplate:
    """Keep custom prompts aligned with ReActAgent's actual action space.

    ReActAgent populates action_space from the bound ToolPack for each reply.
    A custom template must include it rather than replace it with a static list.
    Rendering descriptions as variables also preserves literal JSON/references.
    """
    sections = [workflow_prompt]
    if financial_enabled:
        sections.append(FINANCIAL_AGENT_PROMPT)
    sections.append(REGISTERED_TOOLS_PROMPT)
    return PromptTemplate(
        template="\n\n".join(sections),
        input_variables=["action_space", "action_space_names"],
        template_format="jinja2",
    )
