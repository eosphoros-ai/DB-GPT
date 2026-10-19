"""Custom ReAct prompts must describe the tools the agent can actually execute."""

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
from dbgpt.agent.resource import ToolPack
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.util.react_parser import ReActOutputParser
from dbgpt_app.openapi.api_v1.react_prompt import build_react_prompt_template
from dbgpt_app.openapi.api_v1.tools.financial_tools import make_financial_tools
from dbgpt_app.openapi.api_v1.tools.knowledge_retrieve import make_knowledge_retrieve
from dbgpt_app.openapi.api_v1.tools.skill_tools import (
    make_execute_skill_script_file,
    make_load_skill,
)


async def render_prompt(pack, *, financial_enabled=True):
    agent = (
        ToolCallingReActAgent()
        .bind(AgentContext(conv_id="prompt-test", language="en"))
        .bind(pack)
        .bind(
            build_react_prompt_template(
                "Follow the loaded skill.", financial_enabled=financial_enabled
            )
        )
    )
    reply = await agent._a_init_reply_message(AgentMessage(content="分析这份财报"))
    return await agent.build_system_prompt(context=reply.context)


@pytest.mark.asyncio
@pytest.mark.parametrize("preselected", [False, True])
async def test_financial_tools_are_described_with_executable_names_and_parameters(
    preselected,
):
    state = {}
    financial_tools = make_financial_tools(state)
    tools = [make_execute_skill_script_file(state), Terminate()] + financial_tools
    if not preselected:
        tools += [make_load_skill(state), make_knowledge_retrieve(state, [])]
    pack = ToolPack(tools)
    prompt = await render_prompt(pack)
    inventory = prompt.split("## Available Tools Description\n", 1)[1]

    for registered in pack.sub_resources:
        description, _ = await registered.get_prompt(lang="en")
        assert description in inventory
    assert '"name": "file_id"' in inventory
    assert '"required": false' in inventory
    assert '"name": "findings"' in inventory
    assert '"name": "reviews"' in inventory
    assert "semantic_search" not in inventory
    assert ("load_skill:" in inventory) is (not preselected)
    assert "不是 Skill 脚本或 .py 文件" in prompt

    # The direct-call example is valid ReAct and resolves to the registered
    # preparation tool, with the empty input required for a single PDF.
    example = prompt.split("准备步骤直接输出：\n", 1)[1].split("\n有多份 PDF", 1)[0]
    parsed = ReActOutputParser().parse(example)[0]
    assert parsed.action == "prepare_financial_report"
    assert parsed.action_input == {}
    assert pack._get_execution_tool(parsed.action).name == parsed.action
    terminal_example = inventory.split(
        "return the user-facing answer through the registered terminate tool:\n", 1
    )[1].split("\nPut only", 1)[0]
    terminal_step = ReActOutputParser().parse(terminal_example)[0]
    assert terminal_step.action == "terminate"
    assert terminal_step.action_input == {"output": "final answer"}
    assert "output" in pack._get_execution_tool("terminate").args


@pytest.mark.asyncio
async def test_knowledge_inventory_does_not_advertise_unregistered_financial_tools():
    pack = ToolPack([make_knowledge_retrieve({}, []), Terminate()])
    prompt = await render_prompt(pack, financial_enabled=False)
    assert "knowledge_retrieve:" in prompt
    assert "prepare_financial_report" not in prompt
    assert "semantic_search" not in prompt


@pytest.mark.asyncio
async def test_tool_descriptions_preserve_literal_references_and_nested_packs():
    @tool(description='Returns {{fact:revenue}} and JSON {"value": 1}.')
    def example_tool(file_id: str = "") -> str:
        return ""

    pack = ToolPack([ToolPack([example_tool]), Terminate()])
    prompt = await render_prompt(pack, financial_enabled=False)
    assert "{{fact:revenue}}" in prompt
    assert '{"value": 1}' in prompt
    assert "example_tool:" in prompt
    assert "{{ action_space }}" not in prompt
