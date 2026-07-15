from unittest.mock import MagicMock

from dbgpt_serve.file.service.fsspec_impl import DBGPTFileSystem


def test_rm_uses_bucket_from_simplified_path():
    client = MagicMock()
    client.storage_system.get_file_metadata.return_value = object()
    client.delete_file_by_id.return_value = True
    filesystem = DBGPTFileSystem(client=client)

    filesystem.rm("documents/file.txt")

    client.delete_file_by_id.assert_called_once_with("documents", "file.txt")
