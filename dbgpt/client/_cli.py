"""CLI for DB-GPT client."""

import functools
import json
import time
import uuid
from typing import Any, Dict

import click

from dbgpt.util import get_or_create_event_loop
from dbgpt.util.console import CliLogger
from dbgpt.util.i18n_utils import _

from .client import Client
from .flow import list_flow

cl = CliLogger()


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


@click.command(name="flow")
@add_base_flow_options
@add_chat_options
def run_flow(name: str, uid: str, data: str, interactive: bool, **kwargs):
    """Run a AWEL flow."""
    client = Client()

    loop = get_or_create_event_loop()
    res = loop.run_until_complete(list_flow(client, name, uid))

    if not res:
        cl.error("Flow not found with the given name or uid", exit_code=1)
    if len(res) > 1:
        cl.error("More than one flow found", exit_code=1)
    flow = res[0]
    json_data = _parse_json_data(data, **kwargs)
    json_data["chat_param"] = flow.uid
    json_data["chat_mode"] = "chat_flow"
    stream = "stream" in json_data and str(json_data["stream"]).lower() in ["true", "1"]
    if stream:
        loop.run_until_complete(_chat_stream(client, interactive, json_data))
    else:
        loop.run_until_complete(_chat(client, interactive, json_data))


def _parse_json_data(data: str, **kwargs):
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


async def _chat_stream(client: Client, interactive: bool, json_data: Dict[str, Any]):
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
            cl.info("Chat stream started")
            cl.debug(f"JSON data: {json.dumps(json_data, ensure_ascii=False)}")
            full_text = ""
            cl.print("Bot: ")
            async for out in client.chat_stream(**json_data):
                if out.choices:
                    text = out.choices[0].delta.content
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


async def _chat(client: Client, interactive: bool, json_data: Dict[str, Any]):
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

            cl.info("Chat started")
            cl.debug(f"JSON data: {json.dumps(json_data, ensure_ascii=False)}")
            res = await client.chat(**json_data)
            cl.print("Bot: ")
            if res.choices:
                text = res.choices[0].message.content
                cl.markdown(text)
            time_cost = round(time.time() - start_time, 2)
            cl.success(f"\n:tada: Chat stream finished, timecost: {time_cost} s")
        except Exception as e:
            cl.error(f"Chat failed: {e}", exit_code=1)
        finally:
            first_message = False
            if interactive:
                user_input = ""
            else:
                break
