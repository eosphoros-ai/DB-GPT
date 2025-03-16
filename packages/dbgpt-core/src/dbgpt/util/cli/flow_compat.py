import copy
import json
import os
from typing import List, Optional, Tuple, Union

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
@click.option(
    "--update-template",
    is_flag=True,
    default=False,
    required=False,
    help=_("Update the template file."),
)
def gen_compat(
    module: Optional[str],
    output: Optional[str],
    curr_version: Optional[str],
    last_support_version: Optional[str],
    update_template: bool = False,
):
    """Generate the compatibility flow mapping file."""
    from dbgpt.util.cli._module import _scan_awel_flow

    lang = os.getenv("LANGUAGE")

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
    save_compat = True
    if not user_input or user_input.lower() != "y":
        clog.info("Cancelled")
        save_compat = False
    if save_compat:
        with open(output_file, "w") as f:
            import json

            json.dump(output_dicts, f, ensure_ascii=False, indent=4)

    if update_template:
        _update_template(output_dicts, lang=lang)


def _update_template(
    compat_data: dict, template_file: Optional[str] = None, lang: str = "en"
):
    from dbgpt.core.awel.dag.base import DAGNode
    from dbgpt.core.awel.flow.base import (
        _TYPE_REGISTRY,
    )
    from dbgpt.core.awel.flow.compat import (
        FlowCompatMetadata,
        _register_flow_compat,
        get_new_class_name,
    )
    from dbgpt.core.awel.flow.flow_factory import (
        ResourceMetadata,
        ViewMetadata,
        fill_flow_panel,
    )
    from dbgpt_serve.flow.api.schemas import ServerResponse
    from dbgpt_serve.flow.service.service import (
        _get_flow_templates_from_files,
        _parse_flow_template_from_json,
    )

    last_support_version = compat_data["last_support_version"]
    curr_version = compat_data["curr_version"]

    for data in compat_data["compat"]:
        metadata = FlowCompatMetadata(**data)
        _register_flow_compat(curr_version, last_support_version, metadata)

    templates: List[Tuple[str, ServerResponse]] = []
    if template_file:
        with open(template_file, "r") as f:
            data = json.load(f)
            templates.append((template_file, _parse_flow_template_from_json(data)))
    else:
        templates.extend(_get_flow_templates_from_files(lang))

    new_templates: List[Tuple[str, ServerResponse]] = []

    def metadata_func(old_metadata: Union[ViewMetadata, ResourceMetadata]):
        type_cls = old_metadata.type_cls
        if type_cls in _TYPE_REGISTRY:
            return None
        new_type_cls = None
        try:
            new_type_cls = get_new_class_name(type_cls)
            if not new_type_cls or new_type_cls not in _TYPE_REGISTRY:
                return None
            obj_type = _TYPE_REGISTRY[new_type_cls]
            if isinstance(old_metadata, ViewMetadata):
                if not isinstance(obj_type, DAGNode):
                    return None
                obj_type.metadata
            elif isinstance(old_metadata, ResourceMetadata):
                metadata_attr = f"_resource_metadata_{obj_type.__name__}"
                return getattr(obj_type, metadata_attr)
            else:
                raise ValueError(f"Unknown metadata type: {type(old_metadata)}")
        except Exception as e:
            clog.warning(
                f"Error get metadata for {type_cls}: {str(e)}, new_type_cls: "
                f"{new_type_cls}"
            )
            return None

    for template_file, template in templates:
        new_flow_template = copy.deepcopy(template)
        try:
            fill_flow_panel(
                new_flow_template,
                metadata_func,
                ignore_options_error=True,
                update_id=True,
            )
            new_templates.append((template_file, new_flow_template))
        except Exception as e:
            import traceback

            traceback.print_exc()
            clog.warning(f"Error fill flow panel for {template_file}: {str(e)}")

    user_input = clog.ask("Do you want to update the template file?(y/n)")
    if not user_input or user_input.lower() != "y":
        clog.info("Cancelled")
        return
    for template_file, flow in new_templates:
        template_dict = {"flow": flow.model_dump()}
        dag_json = json.dumps(template_dict, indent=4, ensure_ascii=False)
        with open(template_file, "w") as f:
            f.write(dag_json)
