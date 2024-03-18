import asyncio

from dbgpt.client.client import Client
from dbgpt.client.knowledge import list_space

"""Client: Simple Knowledge CRUD example

    This example demonstrates how to use the dbgpt client to create, get, update, and delete knowledge spaces and documents.
    Example:
    .. code-block:: python

        DBGPT_API_KEY = "dbgpt"
        client = Client(api_key=DBGPT_API_KEY)
        # 1. Create a space
        res = await create_space(
            client,
            SpaceModel(
                name="test_space",
                vector_type="Chroma",
                desc="for client space",
                owner="dbgpt",
            ),
        )
        # 2. Update a space
        res = await update_space(
            client,
            SpaceModel(
                name="test_space",
                vector_type="Chroma",
                desc="for client space333",
                owner="dbgpt",
            ),
        )
        # 3. Delete a space
        res = await delete_space(client, space_id="37")
        # 4. Get a space
        res = await get_space(client, space_id="5")
        # 5. List all spaces
        res = await list_space(client)
        # 6. Create a document
        res = await create_document(
            client,
            DocumentModel(
                space_id="5",
                doc_name="test_doc",
                doc_type="TEXT",
                doc_content="test content",
                doc_source="",
            ),
        )
        # 7. Sync a document
        res = await sync_document(
            client,
            sync_model=SyncModel(
                doc_id="153",
                space_id="40",
                model_name="text2vec",
                chunk_parameters=ChunkParameters(chunk_strategy="Automatic"),
            ),
        )
        # 8. Get a document
        res = await get_document(client, "52")
        # 9. List all documents
        res = await list_document(client)
        # 10. Delete a document
        res = await delete_document(client, "150")
"""


async def main():
    # initialize client
    DBGPT_API_KEY = "dbgpt"
    client = Client(api_key=DBGPT_API_KEY)

    # list all spaces
    res = await list_space(client)
    print(res.json())

    # get space
    # res = await get_space(client, space_id='5')

    # create space
    # res = await create_space(client, SpaceModel(name="test_space", vector_type="Chroma", desc="for client space", owner="dbgpt"))

    # update space
    # res = await update_space(client, SpaceModel(name="test_space", vector_type="Chroma", desc="for client space333", owner="dbgpt"))

    # delete space
    # res = await delete_space(client, space_id='37')

    # list all documents
    # res = await list_document(client)

    # get document
    # res = await get_document(client, "52")

    # delete document
    # res = await delete_document(client, "150")

    # create document
    # res = await create_document(client, DocumentModel(space_id="5", doc_name="test_doc", doc_type="test", doc_content="test content"
    #                                                   , doc_file=('your_file_name', open('{your_file_path}', 'rb'))))

    # sync document
    # res = await sync_document(client, sync_model=SyncModel(doc_id="153", space_id="40", model_name="text2vec", chunk_parameters=ChunkParameters(chunk_strategy="Automatic")))


if __name__ == "__main__":
    asyncio.run(main())
