import click
import logging

from pilot.configs.model_config import DATASETS_DIR

API_ADDRESS: str = "http://127.0.0.1:5000"

logger = logging.getLogger("dbgpt_cli")


@click.group("knowledge")
@click.option(
    "--address",
    type=str,
    default=API_ADDRESS,
    required=False,
    show_default=True,
    help=("Address of the Api server."),
)
def knowledge_cli_group(address: str):
    """Knowledge command line tool"""
    global API_ADDRESS
    API_ADDRESS = address


@knowledge_cli_group.command()
@click.option(
    "--vector_name",
    required=False,
    type=str,
    default="default",
    show_default=True,
    help="Your vector store name",
)
@click.option(
    "--vector_store_type",
    required=False,
    type=str,
    default="Chroma",
    show_default=True,
    help="Vector store type",
)
@click.option(
    "--local_doc_dir",
    required=False,
    type=str,
    default=DATASETS_DIR,
    show_default=True,
    help="Your document directory",
)
@click.option(
    "--skip_wrong_doc",
    required=False,
    type=bool,
    default=False,
    is_flag=True,
    show_default=True,
    help="Skip wrong document",
)
@click.option(
    "--max_workers",
    required=False,
    type=int,
    default=None,
    help="The maximum number of threads that can be used to upload document",
)
def load(
    vector_name: str,
    vector_store_type: str,
    local_doc_dir: str,
    skip_wrong_doc: bool,
    max_workers: int,
):
    """Load your local knowledge to DB-GPT"""
    from pilot.server.knowledge._cli.knowledge_client import knowledge_init

    knowledge_init(
        API_ADDRESS,
        vector_name,
        vector_store_type,
        local_doc_dir,
        skip_wrong_doc,
        max_workers,
    )
