import click
import logging
import os
import functools

from dbgpt.configs.model_config import DATASETS_DIR

_DEFAULT_API_ADDRESS: str = "http://127.0.0.1:5000"
API_ADDRESS: str = _DEFAULT_API_ADDRESS

logger = logging.getLogger("dbgpt_cli")


@click.group("knowledge")
@click.option(
    "--address",
    type=str,
    default=API_ADDRESS,
    required=False,
    show_default=True,
    help=(
        "Address of the Api server(If not set, try to read from environment variable: API_ADDRESS)."
    ),
)
def knowledge_cli_group(address: str):
    """Knowledge command line tool"""
    global API_ADDRESS
    if address == _DEFAULT_API_ADDRESS:
        address = os.getenv("API_ADDRESS", _DEFAULT_API_ADDRESS)
    API_ADDRESS = address


def add_knowledge_options(func):
    @click.option(
        "--space_name",
        required=False,
        type=str,
        default="default",
        show_default=True,
        help="Your knowledge space name",
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@knowledge_cli_group.command()
@add_knowledge_options
@click.option(
    "--vector_store_type",
    required=False,
    type=str,
    default="Chroma",
    show_default=True,
    help="Vector store type.",
)
@click.option(
    "--local_doc_path",
    required=False,
    type=str,
    default=DATASETS_DIR,
    show_default=True,
    help="Your document directory or document file path.",
)
@click.option(
    "--skip_wrong_doc",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Skip wrong document.",
)
@click.option(
    "--overwrite",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Overwrite existing document(they has same name).",
)
@click.option(
    "--max_workers",
    required=False,
    type=int,
    default=None,
    help="The maximum number of threads that can be used to upload document.",
)
@click.option(
    "--pre_separator",
    required=False,
    type=str,
    default=None,
    help="Preseparator, this separator is used for pre-splitting before the document is "
    "actually split by the text splitter. Preseparator are not included in the vectorized text. ",
)
@click.option(
    "--separator",
    required=False,
    type=str,
    default=None,
    help="This is the document separator. Currently, only one separator is supported.",
)
@click.option(
    "--chunk_size",
    required=False,
    type=int,
    default=None,
    help="Maximum size of chunks to split.",
)
@click.option(
    "--chunk_overlap",
    required=False,
    type=int,
    default=None,
    help="Overlap in characters between chunks.",
)
def load(
    space_name: str,
    vector_store_type: str,
    local_doc_path: str,
    skip_wrong_doc: bool,
    overwrite: bool,
    max_workers: int,
    pre_separator: str,
    separator: str,
    chunk_size: int,
    chunk_overlap: int,
):
    """Load your local documents to DB-GPT"""
    from dbgpt.app.knowledge._cli.knowledge_client import knowledge_init

    knowledge_init(
        API_ADDRESS,
        space_name,
        vector_store_type,
        local_doc_path,
        skip_wrong_doc,
        overwrite,
        max_workers,
        pre_separator,
        separator,
        chunk_size,
        chunk_overlap,
    )


@knowledge_cli_group.command()
@add_knowledge_options
@click.option(
    "--doc_name",
    required=False,
    type=str,
    default=None,
    help="The document name you want to delete. If doc_name is None, this command will delete the whole space.",
)
@click.option(
    "-y",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Confirm your choice",
)
def delete(space_name: str, doc_name: str, y: bool):
    """Delete your knowledge space or document in space"""
    from dbgpt.app.knowledge._cli.knowledge_client import knowledge_delete

    knowledge_delete(API_ADDRESS, space_name, doc_name, confirm=y)


@knowledge_cli_group.command()
@click.option(
    "--space_name",
    required=False,
    type=str,
    default=None,
    show_default=True,
    help="Your knowledge space name. If None, list all spaces",
)
@click.option(
    "--doc_id",
    required=False,
    type=int,
    default=None,
    show_default=True,
    help="Your document id in knowledge space. If Not None, list all chunks in current document",
)
@click.option(
    "--page",
    required=False,
    type=int,
    default=1,
    show_default=True,
    help="The page for every query",
)
@click.option(
    "--page_size",
    required=False,
    type=int,
    default=20,
    show_default=True,
    help="The page size for every query",
)
@click.option(
    "--show_content",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    help="Query the document content of chunks",
)
@click.option(
    "--output",
    required=False,
    type=click.Choice(["text", "html", "csv", "latex", "json"]),
    default="text",
    help="The output format",
)
def list(
    space_name: str,
    doc_id: int,
    page: int,
    page_size: int,
    show_content: bool,
    output: str,
):
    """List knowledge space"""
    from dbgpt.app.knowledge._cli.knowledge_client import knowledge_list

    knowledge_list(
        API_ADDRESS, space_name, page, page_size, doc_id, show_content, output
    )
