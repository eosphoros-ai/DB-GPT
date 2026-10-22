"""XML protocol fallback must not rewrite already-framed JSON arguments."""

import json

import pytest

from dbgpt.agent.util.react_parser import ReActOutputParser, extract_terminate_output


@pytest.mark.parametrize(
    "output",
    [
        "Data: <pre>[1,2,3]</pre>",
        "Data:\n<pre>\n[1,2,3]\n</pre>\nEnd.",
        "Quoted <sql_query>[1,2,3]</sql_query> and <code>[4,5]</code>.",
    ],
)
@pytest.mark.parametrize("style", ["standard", "no-thought", "markdown", "fenced"])
def test_valid_react_json_preserves_html_exactly(output, style):
    arguments = {"output": output}
    if style == "markdown":
        text = "**Thought**: Done\n**Action**: terminate\n**Action Input**: "
    elif style == "no-thought":
        text = "Action: terminate\nAction Input: "
    else:
        text = "Thought: Done\nAction: terminate\nAction Input: "
    text += json.dumps(arguments, ensure_ascii=False)
    if style == "fenced":
        text = "```text\n" + text + "\n```"
    parser = ReActOutputParser()
    for steps in (parser.parse(text), parser.parse_current_step(text)):
        assert len(steps) == 1
        assert steps[0].action == "terminate"
        assert steps[0].action_input == arguments
        assert parser.get_final_output(steps) == output
    assert extract_terminate_output(text) == output


def test_html_in_nested_tool_arguments_is_not_an_extra_action():
    arguments = {"data": {"html": "<pre>[1,2,3]</pre>"}, "items": [1, 2]}
    text = "Action: html_interpreter\nAction Input: " + json.dumps(arguments)
    steps = ReActOutputParser().parse(text)
    assert len(steps) == 1
    assert steps[0].action == "html_interpreter"
    assert steps[0].action_input == arguments


@pytest.mark.parametrize("prefix", ["", "Thought: Query sales\n"])
def test_top_level_xml_call_is_still_supported(prefix):
    text = prefix + '<sql_query>{"sql":"SELECT 1", "options":{"limit":2}}</sql_query>'
    steps = ReActOutputParser().parse_current_step(text)
    assert len(steps) == 1
    assert steps[0].action == "sql_query"
    assert steps[0].action_input == {"sql": "SELECT 1", "options": {"limit": 2}}


def test_xml_fallback_uses_json_boundaries_inside_html_strings():
    output = 'Data: <pre>[1,2,3]</pre> and </terminate> {"a": 1}'
    text = "<terminate>" + json.dumps({"output": output}) + "</terminate>"
    assert extract_terminate_output(text) == output


def test_native_tool_fallback_preserves_html_in_its_json_arguments():
    output = "Data: <pre>[1,2,3]</pre>"
    text = (
        "<|tool_call_begin|>functions.terminate:0<|tool_call_argument_begin|>"
        + json.dumps({"output": output})
        + "<|tool_call_end|>"
    )
    assert extract_terminate_output(text) == output


def test_xml_fallback_supports_custom_react_prefixes():
    parser = ReActOutputParser(action_prefix="Do:", action_input_prefix="With:")
    steps = parser.parse_current_step('<query>{"sql":"SELECT 1"}</query>')
    assert steps[0].action == "query"
    assert steps[0].action_input == {"sql": "SELECT 1"}


@pytest.mark.parametrize(
    "text",
    [
        'Example:\n```xml\n<sql_query>{"sql":"SELECT 1"}</sql_query>\n```',
        'Example: <sql_query>{"sql":"SELECT 1"}</sql_query>',
        '<sql_query>{"sql": incomplete}</sql_query>',
        '<sql_query>{"sql":"SELECT 1"}</another_tool>',
    ],
)
def test_examples_or_malformed_xml_are_not_executable(text):
    assert ReActOutputParser().parse_current_step(text) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("native_enabled", [False, True])
async def test_agent_terminate_keeps_html_and_entities(native_enabled):
    from dbgpt.agent import AgentContext, AgentMessage
    from dbgpt.agent.expand.actions.react_action import Terminate
    from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
    from dbgpt.agent.resource import ToolPack

    output = "Data:&#x20;<pre>[1,2,3]</pre>&#x20;"
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id="xml-json-regression", enable_native_function_calling=native_enabled
    )
    agent.resource = ToolPack([Terminate()])
    for action in agent.actions:
        action.init_resource(agent.resource)
    response = await agent.act(
        AgentMessage(
            content="Action: terminate\nAction Input: " + json.dumps({"output": output})
        ),
        sender=agent,
        parser=agent.parser,
        enable_parallel=False,
        tool_calls=None,
    )
    assert response.is_exe_success
    assert response.terminate
    assert response.content == output
