"""CLI for DB-GPT client."""

import asyncio
import functools
import json
import time
import uuid
from typing import Any, AsyncIterator, Callable, Dict, Tuple, cast

import click

from dbgpt.component import SystemApp
from dbgpt.core.awel import DAG, BaseOperator, DAGVar
from dbgpt.core.awel.dag.dag_manager import DAGMetadata, _parse_metadata
from dbgpt.core.awel.flow.flow_factory import FlowFactory
from dbgpt.util import get_or_create_event_loop
from dbgpt.util.console import CliLogger
from dbgpt.util.i18n_utils import _

from .client import Client
from .flow import list_flow
from .flow import run_flow_cmd as client_run_flow_cmd

cl = CliLogger()

_LOCAL_MODE: bool | None = False
_FILE_PATH: str | None = None


@click.group()
@click.option(
    "--local",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Whether use local mode(run local AWEL file)",
)
@click.option(
    "-f",
    "--file",
    type=str,
    default=None,
    required=False,
    help=_("The path of the AWEL flow"),
)
def flow(local: bool = False, file: str | None = None):
    """Run a AWEL flow."""
    global _LOCAL_MODE, _FILE_PATH
    _LOCAL_MODE = local
    _FILE_PATH = file


def add_base_flow_options(func):
    """Add base flow options to the command."""

    @click.option(
        "-n",
        "--name",
        type=str,
        default=None,
        required=False,
        help=_("The name of the AWEL flow"),
    )
    @click.option(
        "--uid",
        type=str,
        default=None,
        required=False,
        help=_("The uid of the AWEL flow"),
    )
    @functools.wraps(func)
    def _wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return _wrapper


def add_chat_options(func):
    """Add chat options to the command."""

    @click.option(
        "-m",
        "--messages",
        type=str,
        default=None,
        required=False,
        help=_("The messages to run AWEL flow"),
    )
    @click.option(
        "--model",
        type=str,
        default=None,
        required=False,
        help=_("The model name of AWEL flow"),
    )
    @click.option(
        "-s",
        "--stream",
        type=bool,
        default=False,
        required=False,
        is_flag=True,
        help=_("Whether use stream mode to run AWEL flow"),
    )
    @click.option(
        "-t",
        "--temperature",
        type=float,
        default=None,
        required=False,
        help=_("The temperature to run AWEL flow"),
    )
    @click.option(
        "--max_new_tokens",
        type=int,
        default=None,
        required=False,
        help=_("The max new tokens to run AWEL flow"),
    )
    @click.option(
        "--conv_uid",
        type=str,
        default=None,
        required=False,
        help=_("The conversation id of the AWEL flow"),
    )
    @click.option(
        "-d",
        "--data",
        type=str,
        default=None,
        required=False,
        help=_("The json data to run AWEL flow, if set, will overwrite other options"),
    )
    @click.option(
        "-e",
        "--extra",
        type=str,
        default=None,
        required=False,
        help=_("The extra json data to run AWEL flow."),
    )
    @click.option(
        "-i",
        "--interactive",
        type=bool,
        default=False,
        required=False,
        is_flag=True,
        help=_("Whether use interactive mode to run AWEL flow"),
    )
    @functools.wraps(func)
    def _wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return _wrapper


@flow.command(name="chat")
@add_base_flow_options
@add_chat_options
def run_flow_chat(name: str, uid: str, data: str, interactive: bool, **kwargs):
    """Run a AWEL flow."""
    json_data = _parse_chat_json_data(data, **kwargs)
    stream = "stream" in json_data and str(json_data["stream"]).lower() in ["true", "1"]
    loop = get_or_create_event_loop()
    if _LOCAL_MODE:
        _run_flow_chat_local(loop, name, interactive, json_data, stream)
        return

    client = Client()

    # AWEL flow store the python module name now, so we need to replace "-" with "_"
    new_name = name.replace("-", "_")
    res = loop.run_until_complete(list_flow(client, new_name, uid))

    if not res:
        cl.error("Flow not found with the given name or uid", exit_code=1)
    if len(res) > 1:
        cl.error("More than one flow found", exit_code=1)
    flow = res[0]
    json_data["chat_param"] = flow.uid
    json_data["chat_mode"] = "chat_flow"
    if stream:
        _run_flow_chat_stream(loop, client, interactive, json_data)
    else:
        _run_flow_chat(loop, client, interactive, json_data)


@flow.command(name="cmd")
@add_base_flow_options
@click.option(
    "-d",
    "--data",
    type=str,
    default=None,
    required=False,
    help=_("The json data to run AWEL flow, if set, will overwrite other options"),
)
@click.option(
    "--output_key",
    type=str,
    default=None,
    required=False,
    help=_(
        "The output key of the AWEL flow, if set, it will try to get the output by the "
        "key"
    ),
)
def run_flow_cmd(
    name: str, uid: str, data: str | None = None, output_key: str | None = None
):
    """Run a AWEL flow with command mode."""
    json_data = _parse_json_data(data)
    loop = get_or_create_event_loop()

    if _LOCAL_MODE:
        _run_flow_cmd_local(loop, name, json_data, output_key)
    else:
        _run_flow_cmd(loop, name, uid, json_data, output_key)


def _run_flow_cmd_local(
    loop: asyncio.BaseEventLoop,
    name: str,
    data: Dict[str, Any] | None = None,
    output_key: str | None = None,
):
    from dbgpt.core.awel.util.chat_util import safe_chat_stream_with_dag_task

    end_node, dag, dag_metadata, call_body = _parse_and_check_local_dag(
        name, _FILE_PATH, data
    )

    async def _streaming_call():
        start_time = time.time()
        try:
            cl.debug("[~info] Flow started")
            cl.debug(f"[~info] JSON data: {json.dumps(data, ensure_ascii=False)}")
            cl.debug("Command output: ")
            async for out in safe_chat_stream_with_dag_task(
                end_node, call_body, incremental=True, covert_to_str=True
            ):
                if not out.success:
                    cl.error(out.text)
                else:
                    cl.print(out.gen_text_with_thinking(), end="")
        except Exception as e:
            cl.error(f"Failed to run flow: {e}", exit_code=1)
        finally:
            time_cost = round(time.time() - start_time, 2)
            cl.success(f"\n:tada: Flow finished, timecost: {time_cost} s")

    loop.run_until_complete(_streaming_call())


def _run_flow_cmd(
    loop: asyncio.BaseEventLoop,
    name: str | None = None,
    uid: str | None = None,
    json_data: Dict[str, Any] | None = None,
    output_key: str | None = None,
):
    client = Client()

    def _non_streaming_callback(text: str):
        parsed_text: Any = None
        if output_key:
            try:
                json_out = json.loads(text)
                parsed_text = json_out.get(output_key)
            except Exception as e:
                cl.warning(f"Failed to parse output by key: {output_key}, {e}")
        if not parsed_text:
            parsed_text = text
        cl.markdown(parsed_text)

    def _streaming_callback(text: str):
        cl.print(text, end="")

    async def _client_run_cmd():
        cl.debug("[~info] Flow started")
        cl.debug(f"[~info] JSON data: {json.dumps(json_data, ensure_ascii=False)}")
        cl.debug("Command output: ")
        start_time = time.time()
        # AWEL flow store the python module name now, so we need to replace "-" with "_"
        new_name = name.replace("-", "_")
        try:
            await client_run_flow_cmd(
                client,
                new_name,
                uid,
                json_data,
                non_streaming_callback=_non_streaming_callback,
                streaming_callback=_streaming_callback,
            )
        except Exception as e:
            cl.error(f"Failed to run flow: {e}", exit_code=1)
        finally:
            time_cost = round(time.time() - start_time, 2)
            cl.success(f"\n:tada: Flow finished, timecost: {time_cost} s")

    loop.run_until_complete(_client_run_cmd())


def _parse_and_check_local_dag(
    name: str,
    filepath: str | None = None,
    data: Dict[str, Any] | None = None,
) -> Tuple[BaseOperator, DAG, DAGMetadata, Any]:
    dag, dag_metadata = _parse_local_dag(name, filepath)

    return _check_local_dag(dag, dag_metadata, data)


def _check_local_dag(
    dag: DAG, dag_metadata: DAGMetadata, data: Dict[str, Any] | None = None
) -> Tuple[BaseOperator, DAG, DAGMetadata, Any]:
    from dbgpt.core.awel import HttpTrigger

    leaf_nodes = dag.leaf_nodes
    if not leaf_nodes:
        cl.error("No leaf nodes found in the flow", exit_code=1)
    if len(leaf_nodes) > 1:
        cl.error("More than one leaf nodes found in the flow", exit_code=1)
    if not isinstance(leaf_nodes[0], BaseOperator):
        cl.error("Unsupported leaf node type", exit_code=1)
    end_node = cast(BaseOperator, leaf_nodes[0])
    call_body: Any = data
    trigger_nodes = dag.trigger_nodes
    if trigger_nodes:
        if len(trigger_nodes) > 1:
            cl.error("More than one trigger nodes found in the flow", exit_code=1)
        trigger = trigger_nodes[0]
        if isinstance(trigger, HttpTrigger):
            http_trigger = trigger
            if http_trigger._req_body and data:
                call_body = http_trigger._req_body(**data)
        else:
            cl.error("Unsupported trigger type", exit_code=1)
    return end_node, dag, dag_metadata, call_body


def _parse_local_dag(name: str, filepath: str | None = None) -> Tuple[DAG, DAGMetadata]:
    system_app = SystemApp()
    DAGVar.set_current_system_app(system_app)

    if not filepath:
        # Load DAG from installed package(dbgpts)
        from dbgpt.util.dbgpts.loader import (
            _flow_package_to_flow_panel,
            _load_flow_package_from_path,
        )

        flow_panel = _flow_package_to_flow_panel(_load_flow_package_from_path(name))
        if flow_panel.define_type == "json":
            factory = FlowFactory()
            factory.pre_load_requirements(flow_panel)
            dag = factory.build(flow_panel)
        else:
            dag = flow_panel.flow_dag
        return dag, _parse_metadata(dag)
    else:
        from dbgpt.core.awel.dag.loader import _process_file

        dags = _process_file(filepath)
        if not dags:
            cl.error("No DAG found in the file", exit_code=1)
        if len(dags) > 1:
            dags = [dag for dag in dags if dag.dag_id == name]
            # Filter by name
            if len(dags) > 1:
                cl.error("More than one DAG found in the file", exit_code=1)
        if not dags:
            cl.error("No DAG found with the given name", exit_code=1)
        return dags[0], _parse_metadata(dags[0])


def _parse_chat_json_data(data: str, **kwargs):
    json_data = {}
    if data:
        try:
            json_data = json.loads(data)
        except Exception as e:
            cl.error(f"Invalid JSON data: {data}, {e}", exit_code=1)
    if "extra" in kwargs and kwargs["extra"]:
        try:
            extra = json.loads(kwargs["extra"])
            kwargs["extra"] = extra
        except Exception as e:
            cl.error(f"Invalid extra JSON data: {kwargs['extra']}, {e}", exit_code=1)
    for k, v in kwargs.items():
        if v is not None and k not in json_data:
            json_data[k] = v
    if "model" not in json_data:
        json_data["model"] = "__empty__model__"
    return json_data


def _parse_json_data(data: str | None) -> Dict[str, Any] | None:
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception as e:
        cl.error(f"Invalid JSON data: {data}, {e}", exit_code=1)
        # Should not reach here
        return None


def _run_flow_chat_local(
    loop: asyncio.BaseEventLoop,
    name: str,
    interactive: bool,
    json_data: Dict[str, Any],
    stream: bool,
):
    from dbgpt.core.awel.util.chat_util import (
        parse_single_output,
        safe_chat_stream_with_dag_task,
    )

    dag, dag_metadata = _parse_local_dag(name, _FILE_PATH)

    async def _streaming_call(_call_body: Dict[str, Any]):
        nonlocal dag, dag_metadata

        end_node, dag, dag_metadata, handled_call_body = _check_local_dag(
            dag, dag_metadata, _call_body
        )
        async for out in safe_chat_stream_with_dag_task(
            end_node, handled_call_body, incremental=True, covert_to_str=True
        ):
            if not out.success:
                cl.error(f"Error: {out.text}")
                raise Exception(out.text)
            else:
                yield out.gen_text_with_thinking()

    async def _call(_call_body: Dict[str, Any]):
        nonlocal dag, dag_metadata

        end_node, dag, dag_metadata, handled_call_body = _check_local_dag(
            dag, dag_metadata, _call_body
        )
        res = await end_node.call(handled_call_body)
        parsed_res = parse_single_output(res, is_sse=False, covert_to_str=True)
        if not parsed_res.success:
            raise Exception(parsed_res.text)
        return parsed_res.text

    if stream:
        loop.run_until_complete(_chat_stream(_streaming_call, interactive, json_data))
    else:
        loop.run_until_complete(_chat(_call, interactive, json_data))


def _run_flow_chat_stream(
    loop: asyncio.BaseEventLoop,
    client: Client,
    interactive: bool,
    json_data: Dict[str, Any],
):
    async def _streaming_call(_call_body: Dict[str, Any]):
        async for out in client.chat_stream(**_call_body):
            if out.choices:
                text = out.choices[0].delta.content
                reasoning_content = out.choices[0].delta.reasoning_content
                if reasoning_content:
                    yield reasoning_content
                if text:
                    yield text

    loop.run_until_complete(_chat_stream(_streaming_call, interactive, json_data))


def _run_flow_chat(
    loop: asyncio.BaseEventLoop,
    client: Client,
    interactive: bool,
    json_data: Dict[str, Any],
):
    async def _call(_call_body: Dict[str, Any]):
        res = await client.chat(**_call_body)
        if res.choices:
            text = res.choices[0].message.content
            if res.choices[0].message.reasoning_content:
                reasoning_content = res.choices[0].message.reasoning_content
                # For each line, add '>' at the beginning
                reasoning_content = "\n".join(
                    [f"> {line}" for line in reasoning_content.split("\n")]
                )
                text = reasoning_content + "\n\n" + text
            return text

    loop.run_until_complete(_chat(_call, interactive, json_data))


async def _chat_stream(
    streaming_func: Callable[[Dict[str, Any]], AsyncIterator[str]],
    interactive: bool,
    json_data: Dict[str, Any],
):
    user_input = json_data.get("messages", "")
    if "conv_uid" not in json_data and interactive:
        json_data["conv_uid"] = str(uuid.uuid4())
    first_message = True
    while True:
        try:
            if interactive and not user_input:
                cl.print("Type 'exit' or 'quit' to exit.")
                while not user_input:
                    user_input = cl.ask("You")
            if user_input.lower() in ["exit", "quit", "q"]:
                break
            start_time = time.time()
            json_data["messages"] = user_input
            if first_message:
                cl.info("You: " + user_input)
            cl.debug("[~info] Chat stream started")
            cl.debug(f"[~info] JSON data: {json.dumps(json_data, ensure_ascii=False)}")
            full_text = ""
            cl.print("Bot: ")
            async for text in streaming_func(json_data):
                if text:
                    full_text += text
                    cl.print(text, end="")
            end_time = time.time()
            time_cost = round(end_time - start_time, 2)
            cl.success(f"\n:tada: Chat stream finished, timecost: {time_cost} s")
        except Exception as e:
            cl.error(f"Chat stream failed: {e}", exit_code=1)
        finally:
            first_message = False
            if interactive:
                user_input = ""
            else:
                break


async def _chat(
    func: Callable[[Dict[str, Any]], Any],
    interactive: bool,
    json_data: Dict[str, Any],
):
    user_input = json_data.get("messages", "")
    if "conv_uid" not in json_data and interactive:
        json_data["conv_uid"] = str(uuid.uuid4())
    first_message = True
    while True:
        try:
            if interactive and not user_input:
                cl.print("Type 'exit' or 'quit' to exit.")
                while not user_input:
                    user_input = cl.ask("You")
            if user_input.lower() in ["exit", "quit", "q"]:
                break
            start_time = time.time()
            json_data["messages"] = user_input
            if first_message:
                cl.info("You: " + user_input)

            cl.debug("[~info] Chat started")
            cl.debug(f"[~info] JSON data: {json.dumps(json_data, ensure_ascii=False)}")
            res = await func(json_data)
            cl.print("Bot: ")
            if res:
                cl.markdown(res)
            time_cost = round(time.time() - start_time, 2)
            cl.success(f"\n:tada: Chat stream finished, timecost: {time_cost} s")
        except Exception as e:
            import traceback

            messages = traceback.format_exc()
            cl.error(f"Chat failed: {e}\n, error detail: {messages}", exit_code=1)
        finally:
            first_message = False
            if interactive:
                user_input = ""
            else:
                break
