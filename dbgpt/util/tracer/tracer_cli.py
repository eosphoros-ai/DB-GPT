import glob
import json
import logging
import os
from datetime import datetime
from typing import Callable, Dict, Iterable

import click

from dbgpt.configs.model_config import LOGDIR
from dbgpt.util.tracer import SpanType, SpanTypeRunName

logger = logging.getLogger("dbgpt_cli")


_DEFAULT_FILE_PATTERN = os.path.join(LOGDIR, "dbgpt*.jsonl")


@click.group("trace")
def trace_cli_group():
    """Analyze and visualize trace spans."""
    pass


@trace_cli_group.command()
@click.option(
    "--trace_id",
    required=False,
    type=str,
    default=None,
    show_default=True,
    help="Specify the trace ID to list",
)
@click.option(
    "--span_id",
    required=False,
    type=str,
    default=None,
    show_default=True,
    help="Specify the Span ID to list.",
)
@click.option(
    "--span_type",
    required=False,
    type=str,
    default=None,
    show_default=True,
    help="Specify the Span Type to list.",
)
@click.option(
    "--parent_span_id",
    required=False,
    type=str,
    default=None,
    show_default=True,
    help="Specify the Parent Span ID to list.",
)
@click.option(
    "--search",
    required=False,
    type=str,
    default=None,
    show_default=True,
    help="Search trace_id, span_id, parent_span_id, operation_name or content in metadata.",
)
@click.option(
    "-l",
    "--limit",
    type=int,
    default=20,
    help="Limit the number of recent span displayed.",
)
@click.option(
    "--start_time",
    type=str,
    help='Filter by start time. Format: "YYYY-MM-DD HH:MM:SS.mmm"',
)
@click.option(
    "--end_time", type=str, help='Filter by end time. Format: "YYYY-MM-DD HH:MM:SS.mmm"'
)
@click.option(
    "--desc",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Whether to use reverse sorting. By default, sorting is based on start time.",
)
@click.option(
    "--output",
    required=False,
    type=click.Choice(["text", "html", "csv", "latex", "json"]),
    default="text",
    help="The output format",
)
@click.argument("files", nargs=-1, type=click.Path(exists=True, readable=True))
def list(
    trace_id: str,
    span_id: str,
    span_type: str,
    parent_span_id: str,
    search: str,
    limit: int,
    start_time: str,
    end_time: str,
    desc: bool,
    output: str,
    files=None,
):
    """List your trace spans"""
    from prettytable import PrettyTable

    # If no files are explicitly specified, use the default pattern to get them
    spans = read_spans_from_files(files)

    if trace_id:
        spans = filter(lambda s: s["trace_id"] == trace_id, spans)
    if span_id:
        spans = filter(lambda s: s["span_id"] == span_id, spans)
    if span_type:
        spans = filter(lambda s: s["span_type"] == span_type, spans)
    if parent_span_id:
        spans = filter(lambda s: s["parent_span_id"] == parent_span_id, spans)
    # Filter spans based on the start and end times
    if start_time:
        start_dt = _parse_datetime(start_time)
        spans = filter(
            lambda span: _parse_datetime(span["start_time"]) >= start_dt, spans
        )

    if end_time:
        end_dt = _parse_datetime(end_time)
        spans = filter(
            lambda span: _parse_datetime(span["start_time"]) <= end_dt, spans
        )

    if search:
        spans = filter(_new_search_span_func(search), spans)

    # Sort spans based on the start time
    spans = sorted(
        spans, key=lambda span: _parse_datetime(span["start_time"]), reverse=desc
    )[:limit]

    table = PrettyTable(
        ["Trace ID", "Span ID", "Operation Name", "Conversation UID"],
    )

    for sp in spans:
        conv_uid = None
        if "metadata" in sp and sp:
            metadata = sp["metadata"]
            if isinstance(metadata, dict):
                conv_uid = metadata.get("conv_uid")
        table.add_row(
            [
                sp.get("trace_id"),
                sp.get("span_id"),
                # sp.get("parent_span_id"),
                sp.get("operation_name"),
                conv_uid,
            ]
        )
    out_kwargs = {"ensure_ascii": False} if output == "json" else {}
    print(table.get_formatted_string(out_format=output, **out_kwargs))


@trace_cli_group.command()
@click.option(
    "--trace_id",
    required=True,
    type=str,
    help="Specify the trace ID to list",
)
@click.argument("files", nargs=-1, type=click.Path(exists=True, readable=True))
def tree(trace_id: str, files):
    """Display trace links as a tree"""
    hierarchy = _view_trace_hierarchy(trace_id, files)
    if not hierarchy:
        _print_empty_message(files)
        return
    _print_trace_hierarchy(hierarchy)


@trace_cli_group.command()
@click.option(
    "--trace_id",
    required=False,
    type=str,
    default=None,
    help="Specify the trace ID to analyze. If None, show latest conversation details",
)
@click.option(
    "--tree",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Display trace spans as a tree",
)
@click.option(
    "--hide_conv",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Hide your conversation details",
)
@click.option(
    "--hide_run_params",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Hide run params",
)
@click.option(
    "--output",
    required=False,
    type=click.Choice(["text", "html", "csv", "latex", "json"]),
    default="text",
    help="The output format",
)
@click.argument("files", nargs=-1, type=click.Path(exists=False, readable=True))
def chat(
    trace_id: str,
    tree: bool,
    hide_conv: bool,
    hide_run_params: bool,
    output: str,
    files,
):
    """Show conversation details"""
    from prettytable import PrettyTable

    spans = read_spans_from_files(files)

    # Sort by start time
    spans = sorted(
        spans, key=lambda span: _parse_datetime(span["start_time"]), reverse=True
    )
    spans = [sp for sp in spans]
    if not spans:
        _print_empty_message(files)
        return
    service_spans = {}
    service_names = set(SpanTypeRunName.values())
    found_trace_id = None
    for sp in spans:
        span_type = sp["span_type"]
        metadata = sp.get("metadata")
        if span_type == SpanType.RUN:
            service_name = metadata["run_service"]
            service_spans[service_name] = sp.copy()
            if set(service_spans.keys()) == service_names and found_trace_id:
                break
        elif span_type == SpanType.CHAT and not found_trace_id:
            if not trace_id:
                found_trace_id = sp["trace_id"]
            if trace_id and trace_id == sp["trace_id"]:
                found_trace_id = trace_id

    service_tables = {}
    system_infos_table = {}
    out_kwargs = {"ensure_ascii": False} if output == "json" else {}
    for service_name, sp in service_spans.items():
        metadata = sp["metadata"]
        table = PrettyTable(["Config Key", "Config Value"], title=service_name)
        for k, v in metadata["params"].items():
            table.add_row([k, v])
        service_tables[service_name] = table
        sys_infos = metadata.get("sys_infos")
        if sys_infos and isinstance(sys_infos, dict):
            sys_table = PrettyTable(
                ["System Config Key", "System Config Value"],
                title=f"{service_name} System information",
            )
            for k, v in sys_infos.items():
                sys_table.add_row([k, v])
            system_infos_table[service_name] = sys_table

    if not hide_run_params:
        merged_table1 = merge_tables_horizontally(
            [
                service_tables.get(SpanTypeRunName.WEBSERVER.value),
                service_tables.get(SpanTypeRunName.EMBEDDING_MODEL.value),
            ]
        )
        merged_table2 = merge_tables_horizontally(
            [
                service_tables.get(SpanTypeRunName.MODEL_WORKER.value),
                service_tables.get(SpanTypeRunName.WORKER_MANAGER.value),
            ]
        )
        sys_table = system_infos_table.get(SpanTypeRunName.WORKER_MANAGER.value)
        if system_infos_table:
            for k, v in system_infos_table.items():
                sys_table = v
                break
        if output == "text":
            print(merged_table1)
            print(merged_table2)
        else:
            for service_name, table in service_tables.items():
                print(table.get_formatted_string(out_format=output, **out_kwargs))
        if sys_table:
            print(sys_table.get_formatted_string(out_format=output, **out_kwargs))

    if not found_trace_id:
        print(f"Can't found conversation with trace_id: {trace_id}")
        return
    trace_id = found_trace_id

    trace_spans = [span for span in spans if span["trace_id"] == trace_id]
    trace_spans = [s for s in reversed(trace_spans)]
    hierarchy = _build_trace_hierarchy(trace_spans)
    if tree:
        print(f"\nInvoke Trace Tree(trace_id: {trace_id}):\n")
        _print_trace_hierarchy(hierarchy)

    if hide_conv:
        return

    trace_spans = _get_ordered_trace_from(hierarchy)
    table = PrettyTable(["Key", "Value Value"], title="Chat Trace Details")
    split_long_text = output == "text"

    for sp in trace_spans:
        op = sp["operation_name"]
        metadata = sp.get("metadata")
        if op == "get_chat_instance" and not sp["end_time"]:
            table.add_row(["trace_id", trace_id])
            table.add_row(["span_id", sp["span_id"]])
            table.add_row(["conv_uid", metadata.get("conv_uid")])
            table.add_row(["user_input", metadata.get("user_input")])
            table.add_row(["chat_mode", metadata.get("chat_mode")])
            table.add_row(["select_param", metadata.get("select_param")])
            table.add_row(["model_name", metadata.get("model_name")])
        if op in ["BaseChat.stream_call", "BaseChat.nostream_call"]:
            if not sp["end_time"]:
                table.add_row(["temperature", metadata.get("temperature")])
                table.add_row(["max_new_tokens", metadata.get("max_new_tokens")])
                table.add_row(["echo", metadata.get("echo")])
            elif "error" in metadata:
                table.add_row(["BaseChat Error", metadata.get("error")])
        if op == "BaseChat.do_action" and not sp["end_time"]:
            if "model_output" in metadata:
                table.add_row(
                    [
                        "BaseChat model_output",
                        split_string_by_terminal_width(
                            metadata.get("model_output").get("text"),
                            split=split_long_text,
                        ),
                    ]
                )
            if "ai_response_text" in metadata:
                table.add_row(
                    [
                        "BaseChat ai_response_text",
                        split_string_by_terminal_width(
                            metadata.get("ai_response_text"), split=split_long_text
                        ),
                    ]
                )
            if "prompt_define_response" in metadata:
                prompt_define_response = metadata.get("prompt_define_response") or ""
                if isinstance(prompt_define_response, dict) or isinstance(
                    prompt_define_response, type([])
                ):
                    prompt_define_response = json.dumps(
                        prompt_define_response, ensure_ascii=False
                    )
                table.add_row(
                    [
                        "BaseChat prompt_define_response",
                        split_string_by_terminal_width(
                            prompt_define_response,
                            split=split_long_text,
                        ),
                    ]
                )
        if op == "DefaultModelWorker_call.generate_stream_func":
            if not sp["end_time"]:
                table.add_row(["llm_adapter", metadata.get("llm_adapter")])
                table.add_row(
                    [
                        "User prompt",
                        split_string_by_terminal_width(
                            metadata.get("prompt"), split=split_long_text
                        ),
                    ]
                )
            else:
                table.add_row(
                    [
                        "Model output",
                        split_string_by_terminal_width(metadata.get("output")),
                    ]
                )
        if (
            op
            in [
                "DefaultModelWorker.async_generate_stream",
                "DefaultModelWorker.generate_stream",
            ]
            and metadata
            and "error" in metadata
        ):
            table.add_row(["Model Error", metadata.get("error")])
    print(table.get_formatted_string(out_format=output, **out_kwargs))


def read_spans_from_files(files=None) -> Iterable[Dict]:
    """
    Reads spans from multiple files based on the provided file paths.
    """
    if not files:
        files = [_DEFAULT_FILE_PATTERN]

    for filepath in files:
        for filename in glob.glob(filepath):
            with open(filename, "r") as file:
                for line in file:
                    yield json.loads(line)


def _print_empty_message(files=None):
    if not files:
        files = [_DEFAULT_FILE_PATTERN]
    file_names = ",".join(files)
    print(f"No trace span records found in your tracer files: {file_names}")


def _new_search_span_func(search: str):
    def func(span: Dict) -> bool:
        items = [span["trace_id"], span["span_id"], span["parent_span_id"]]
        if "operation_name" in span:
            items.append(span["operation_name"])
        if "metadata" in span:
            metadata = span["metadata"]
            if isinstance(metadata, dict):
                for k, v in metadata.items():
                    items.append(k)
                    items.append(v)
        return any(search in str(item) for item in items if item)

    return func


def _parse_datetime(dt_str):
    """Parse a datetime string to a datetime object."""
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")


def _build_trace_hierarchy(spans, parent_span_id=None, indent=0):
    # Current spans
    current_level_spans = [
        span
        for span in spans
        if span["parent_span_id"] == parent_span_id and span["end_time"] is None
    ]

    hierarchy = []

    for start_span in current_level_spans:
        # Find end span
        end_span = next(
            (
                span
                for span in spans
                if span["span_id"] == start_span["span_id"]
                and span["end_time"] is not None
            ),
            None,
        )
        entry = {
            "operation_name": start_span["operation_name"],
            "parent_span_id": start_span["parent_span_id"],
            "span_id": start_span["span_id"],
            "start_time": start_span["start_time"],
            "end_time": start_span["end_time"],
            "metadata": start_span["metadata"],
            "children": _build_trace_hierarchy(
                spans, start_span["span_id"], indent + 1
            ),
        }
        hierarchy.append(entry)

        # Append end span
        if end_span:
            entry_end = {
                "operation_name": end_span["operation_name"],
                "parent_span_id": end_span["parent_span_id"],
                "span_id": end_span["span_id"],
                "start_time": end_span["start_time"],
                "end_time": end_span["end_time"],
                "metadata": end_span["metadata"],
                "children": [],
            }
            hierarchy.append(entry_end)

    return hierarchy


def _view_trace_hierarchy(trace_id, files=None):
    """Find and display the calls of the entire link based on the given trace_id"""
    spans = read_spans_from_files(files)
    trace_spans = [span for span in spans if span["trace_id"] == trace_id]
    if not trace_spans:
        return None
    hierarchy = _build_trace_hierarchy(trace_spans)
    return hierarchy


def _print_trace_hierarchy(hierarchy, indent=0):
    """Print link hierarchy"""
    for entry in hierarchy:
        print(
            "  " * indent
            + f"Operation: {entry['operation_name']} (Start: {entry['start_time']}, End: {entry['end_time']})"
        )
        _print_trace_hierarchy(entry["children"], indent + 1)


def _get_ordered_trace_from(hierarchy):
    traces = []

    def func(items):
        for item in items:
            traces.append(item)
            func(item["children"])

    func(hierarchy)
    return traces


def _print(service_spans: Dict):
    for names in [
        [SpanTypeRunName.WEBSERVER.name, SpanTypeRunName.EMBEDDING_MODEL],
        [SpanTypeRunName.WORKER_MANAGER.name, SpanTypeRunName.MODEL_WORKER],
    ]:
        pass


def merge_tables_horizontally(tables):
    from prettytable import PrettyTable

    if not tables:
        return None

    tables = [t for t in tables if t]
    if not tables:
        return None

    max_rows = max(len(table._rows) for table in tables)

    merged_table = PrettyTable()

    new_field_names = []
    for table in tables:
        new_field_names.extend(
            [
                f"{name} ({table.title})" if table.title else f"{name}"
                for name in table.field_names
            ]
        )

    merged_table.field_names = new_field_names

    for i in range(max_rows):
        merged_row = []
        for table in tables:
            if i < len(table._rows):
                merged_row.extend(table._rows[i])
            else:
                # Fill empty cells for shorter tables
                merged_row.extend([""] * len(table.field_names))
        merged_table.add_row(merged_row)

    return merged_table


def split_string_by_terminal_width(s, split=True, max_len=None, sp="\n"):
    """
    Split a string into substrings based on the current terminal width.

    Parameters:
    - s: the input string
    """
    if not split:
        return s
    if not max_len:
        try:
            max_len = int(os.get_terminal_size().columns * 0.8)
        except OSError:
            # Default to 80 columns if the terminal size can't be determined
            max_len = 100
    return sp.join([s[i : i + max_len] for i in range(0, len(s), max_len)])
