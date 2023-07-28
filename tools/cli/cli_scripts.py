#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DB-GPT command line tools. 

You can use it for some background management:
- Lots of knowledge document initialization.
- Load the data into the database.
- Show server status
- ...


Maybe move this to pilot module and append to console_scripts in the future.

"""
import sys
import click
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
)


from pilot.configs.model_config import DATASETS_DIR

from tools.cli.knowledge_client import knowledge_init

API_ADDRESS: str = "http://127.0.0.1:5000"


@click.group()
@click.option(
    "--api_address",
    required=False,
    default="http://127.0.0.1:5000",
    type=str,
    help="Api server address",
)
@click.version_option()
def cli(api_address: str):
    global API_ADDRESS
    API_ADDRESS = api_address


@cli.command()
@click.option(
    "--vector_name",
    required=False,
    type=str,
    default="default",
    help="Your vector store name",
)
@click.option(
    "--vector_store_type",
    required=False,
    type=str,
    default="Chroma",
    help="Vector store type",
)
@click.option(
    "--local_doc_dir",
    required=False,
    type=str,
    default=DATASETS_DIR,
    help="Your document directory",
)
@click.option(
    "--skip_wrong_doc",
    required=False,
    type=bool,
    default=False,
    help="Skip wrong document",
)
@click.option(
    "--max_workers",
    required=False,
    type=int,
    default=None,
    help="The maximum number of threads that can be used to upload document",
)
@click.option(
    "-v",
    "--verbose",
    required=False,
    is_flag=True,
    hidden=True,
    help="Show debuggging information.",
)
def knowledge(
    vector_name: str,
    vector_store_type: str,
    local_doc_dir: str,
    skip_wrong_doc: bool,
    max_workers: int,
    verbose: bool,
):
    """Knowledge command line tool"""
    knowledge_init(
        API_ADDRESS,
        vector_name,
        vector_store_type,
        local_doc_dir,
        skip_wrong_doc,
        verbose,
        max_workers,
    )


# knowledge command
cli.add_command(knowledge)
# TODO add more command


def main():
    return cli()


if __name__ == "__main__":
    main()
