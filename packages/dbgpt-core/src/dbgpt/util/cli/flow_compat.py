import os
from typing import Optional

import click

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.util.console import CliLogger
from dbgpt.util.i18n_utils import _

_DEFAULT_PATH = os.path.join(
    ROOT_PATH, "packages", "dbgpt-serve", "src", "dbgpt_serve", "flow", "compat"
)

clog = CliLogger()


@click.group("flow")
def tool_flow_cli_group():
    """FLow tools."""
    pass


@tool_flow_cli_group.command()
@click.option(
    "--module",
    type=str,
    default=None,
    required=False,
    help=_(
        "The module to scan, if not set, will scan all DB-GPT modules("
        "'dbgpt,dbgpt_client,dbgpt_ext,dbgpt_serve,dbgpt_app')."
    ),
)
@click.option(
    "--output",
    type=str,
    default=None,
    required=False,
    help=_(
        "The output path, if not set, will print to "
        "packages/dbgpt-serve/src/dbgpt_serve/flow/compat/"
    ),
)
@click.option(
    "--curr_version",
    type=str,
    default=None,
    required=False,
    help=_(
        "The current version of the flow, if not set, will read from dbgpt.__version__"
    ),
)
@click.option(
    "--last_support_version",
    type=str,
    default=None,
    required=False,
    help=_(
        "The last version to compatible, if not set, will big than the current version "
        "by one minor version."
    ),
)
def gen_compat(
    module: Optional[str],
    output: Optional[str],
    curr_version: Optional[str],
    last_support_version: Optional[str],
):
    """Generate the compatibility flow mapping file."""
    from ._module import _scan_awel_flow

    modules = []
    if module:
        for m in module.split(","):
            modules.append(m.strip())
    if not output:
        output = _DEFAULT_PATH
    if not curr_version:
        from dbgpt import __version__

        curr_version = __version__
    if not last_support_version:
        last_support_version = curr_version.split(".")
        last_support_version[-2] = str(int(last_support_version[-2]) + 1)
        last_support_version[-1] = "x"
        last_support_version = ".".join(last_support_version)

    output_dicts = {
        "curr_version": curr_version,
        "last_support_version": last_support_version,
        "compat": [],
    }
    flows = _scan_awel_flow(modules)
    for flow in flows:
        output_dicts["compat"].append(flow.to_dict())
    os.makedirs(output, exist_ok=True)
    output_file = os.path.join(output, curr_version + "_compat_flow.json")
    user_input = clog.ask(f"Output to {output_file}, do you want to continue?(y/n)")
    if not user_input or user_input.lower() != "y":
        clog.info("Cancelled")
        return
    with open(output_file, "w") as f:
        import json

        json.dump(output_dicts, f, ensure_ascii=False, indent=4)
