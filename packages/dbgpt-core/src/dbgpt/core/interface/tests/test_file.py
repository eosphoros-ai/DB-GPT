import hashlib
import io
import os
from unittest import mock

import pytest

from ..file import (
    FileMetadata,
    FileMetadataIdentifier,
    FileStorageClient,
    FileStorageSystem,
    InMemoryStorage,
    LocalFileStorage,
    SimpleDistributedStorage,
)


@pytest.fixture
def temp_test_file_dir(tmpdir):
    return str(tmpdir)


@pytest.fixture
def temp_storage_path(tmpdir):
    return str(tmpdir)


@pytest.fixture
def local_storage_backend(temp_storage_path):
    return LocalFileStorage(temp_storage_path)


@pytest.fixture
def distributed_storage_backend(temp_storage_path):
    node_address = "127.0.0.1:8000"
    return SimpleDistributedStorage(node_address, temp_storage_path)


@pytest.fixture
def file_storage_system(local_storage_backend):
    backends = {"local": local_storage_backend}
    metadata_storage = InMemoryStorage()
    return FileStorageSystem(backends, metadata_storage)


@pytest.fixture
def file_storage_client(file_storage_system):
    return FileStorageClient(storage_system=file_storage_system)


@pytest.fixture
def sample_file_path(temp_test_file_dir):
    file_path = os.path.join(temp_test_file_dir, "sample.txt")
    with open(file_path, "wb") as f:
        f.write(b"Sample file content")
    return file_path


@pytest.fixture
def sample_file_data():
    return io.BytesIO(b"Sample file content for distributed storage")


def test_save_file(file_storage_client, sample_file_path):
    bucket = "test-bucket"
    uri = file_storage_client.upload_file(
        bucket=bucket, file_path=sample_file_path, storage_type="local"
    )
    assert uri.startswith("dbgpt-fs://local/test-bucket/")
    assert os.path.exists(sample_file_path)


def test_get_file(file_storage_client, sample_file_path):
    bucket = "test-bucket"
    uri = file_storage_client.upload_file(
        bucket=bucket, file_path=sample_file_path, storage_type="local"
    )
    file_data, metadata = file_storage_client.storage_system.get_file(uri)
    assert file_data.read() == b"Sample file content"
    assert metadata.file_name == "sample.txt"
    assert metadata.bucket == bucket


def test_delete_file(file_storage_client, sample_file_path):
    bucket = "test-bucket"
    uri = file_storage_client.upload_file(
        bucket=bucket, file_path=sample_file_path, storage_type="local"
    )
    assert len(file_storage_client.list_files(bucket=bucket)) == 1
    result = file_storage_client.delete_file(uri)
    assert result is True
    assert len(file_storage_client.list_files(bucket=bucket)) == 0


def test_list_files(file_storage_client, sample_file_path):
    bucket = "test-bucket"
    _uri1 = file_storage_client.upload_file(
        bucket=bucket, file_path=sample_file_path, storage_type="local"
    )
    files = file_storage_client.list_files(bucket=bucket)
    assert len(files) == 1


def test_save_file_unsupported_storage(file_storage_system, sample_file_path):
    bucket = "test-bucket"
    with pytest.raises(ValueError):
        file_storage_system.save_file(
            bucket=bucket,
            file_name="unsupported.txt",
            file_data=io.BytesIO(b"Unsupported storage"),
            storage_type="unsupported",
        )


def test_get_file_not_found(file_storage_system):
    with pytest.raises(FileNotFoundError):
        file_storage_system.get_file("dbgpt-fs://local/test-bucket/nonexistent")


def test_delete_file_not_found(file_storage_system):
    result = file_storage_system.delete_file("dbgpt-fs://local/test-bucket/nonexistent")
    assert result is False


def test_metadata_management(file_storage_system):
    bucket = "test-bucket"
    file_id = "test_file"
    _metadata = file_storage_system.metadata_storage.save(
        FileMetadata(
            file_id=file_id,
            bucket=bucket,
            file_name="test.txt",
            file_size=100,
            storage_type="local",
            storage_path="/path/to/test.txt",
            uri="dbgpt-fs://local/test-bucket/test_file",
            custom_metadata={"key": "value"},
            file_hash="hash",
        )
    )

    loaded_metadata = file_storage_system.metadata_storage.load(
        FileMetadataIdentifier(file_id=file_id, bucket=bucket), FileMetadata
    )
    assert loaded_metadata.file_name == "test.txt"
    assert loaded_metadata.custom_metadata["key"] == "value"
    assert loaded_metadata.bucket == bucket


def test_concurrent_save_and_delete(file_storage_client, sample_file_path):
    bucket = "test-bucket"

    # Simulate concurrent file save and delete operations
    def save_file():
        return file_storage_client.upload_file(
            bucket=bucket, file_path=sample_file_path, storage_type="local"
        )

    def delete_file(uri):
        return file_storage_client.delete_file(uri)

    uri = save_file()

    # Simulate concurrent operations
    save_file()
    delete_file(uri)
    assert len(file_storage_client.list_files(bucket=bucket)) == 1


def test_large_file_handling(file_storage_client, temp_storage_path):
    bucket = "test-bucket"
    large_file_path = os.path.join(temp_storage_path, "large_sample.bin")
    with open(large_file_path, "wb") as f:
        f.write(os.urandom(10 * 1024 * 1024))  # 10 MB file

    uri = file_storage_client.upload_file(
        bucket=bucket,
        file_path=large_file_path,
        storage_type="local",
        custom_metadata={"description": "Large file test"},
    )
    file_data, metadata = file_storage_client.storage_system.get_file(uri)
    assert file_data.read() == open(large_file_path, "rb").read()
    assert metadata.file_name == "large_sample.bin"
    assert metadata.bucket == bucket


def test_file_hash_verification_success(file_storage_client, sample_file_path):
    bucket = "test-bucket"
    # Upload file and
    uri = file_storage_client.upload_file(
        bucket=bucket, file_path=sample_file_path, storage_type="local"
    )

    file_data, metadata = file_storage_client.storage_system.get_file(uri)
    file_hash = metadata.file_hash
    calculated_hash = file_storage_client.storage_system._calculate_file_hash(file_data)

    assert file_hash == calculated_hash, (
        "File hash should match after saving and loading"
    )


def test_file_hash_verification_failure(file_storage_client, sample_file_path):
    bucket = "test-bucket"
    # Upload file and
    uri = file_storage_client.upload_file(
        bucket=bucket, file_path=sample_file_path, storage_type="local"
    )

    # Modify the file content manually to simulate file tampering
    storage_system = file_storage_client.storage_system
    metadata = storage_system.metadata_storage.load(
        FileMetadataIdentifier(file_id=uri.split("/")[-1], bucket=bucket), FileMetadata
    )
    with open(metadata.storage_path, "wb") as f:
        f.write(b"Tampered content")

    # Get file should raise an exception due to hash mismatch
    with pytest.raises(ValueError, match="File integrity check failed. Hash mismatch."):
        storage_system.get_file(uri)


def test_file_isolation_across_buckets(file_storage_client, sample_file_path):
    bucket1 = "bucket1"
    bucket2 = "bucket2"

    # Upload the same file to two different buckets
    uri1 = file_storage_client.upload_file(
        bucket=bucket1, file_path=sample_file_path, storage_type="local"
    )
    uri2 = file_storage_client.upload_file(
        bucket=bucket2, file_path=sample_file_path, storage_type="local"
    )

    # Verify both URIs are different and point to different files
    assert uri1 != uri2

    file_data1, metadata1 = file_storage_client.storage_system.get_file(uri1)
    file_data2, metadata2 = file_storage_client.storage_system.get_file(uri2)

    assert file_data1.read() == b"Sample file content"
    assert file_data2.read() == b"Sample file content"
    assert metadata1.bucket == bucket1
    assert metadata2.bucket == bucket2


def test_list_files_in_specific_bucket(file_storage_client, sample_file_path):
    bucket1 = "bucket1"
    bucket2 = "bucket2"

    # Upload a file to both buckets
    file_storage_client.upload_file(
        bucket=bucket1, file_path=sample_file_path, storage_type="local"
    )
    file_storage_client.upload_file(
        bucket=bucket2, file_path=sample_file_path, storage_type="local"
    )

    # List files in bucket1 and bucket2
    files_in_bucket1 = file_storage_client.list_files(bucket=bucket1)
    files_in_bucket2 = file_storage_client.list_files(bucket=bucket2)

    assert len(files_in_bucket1) == 1
    assert len(files_in_bucket2) == 1
    assert files_in_bucket1[0].bucket == bucket1
    assert files_in_bucket2[0].bucket == bucket2


def test_delete_file_in_one_bucket_does_not_affect_other_bucket(
    file_storage_client, sample_file_path
):
    bucket1 = "bucket1"
    bucket2 = "bucket2"

    # Upload the same file to two different buckets
    uri1 = file_storage_client.upload_file(
        bucket=bucket1, file_path=sample_file_path, storage_type="local"
    )
    uri2 = file_storage_client.upload_file(
        bucket=bucket2, file_path=sample_file_path, storage_type="local"
    )

    # Delete the file in bucket1
    file_storage_client.delete_file(uri1)

    # Check that the file in bucket1 is deleted
    assert len(file_storage_client.list_files(bucket=bucket1)) == 0

    # Check that the file in bucket2 is still there
    assert len(file_storage_client.list_files(bucket=bucket2)) == 1
    file_data2, metadata2 = file_storage_client.storage_system.get_file(uri2)
    assert file_data2.read() == b"Sample file content"


def test_file_hash_verification_in_different_buckets(
    file_storage_client, sample_file_path
):
    bucket1 = "bucket1"
    bucket2 = "bucket2"

    # Upload the file to both buckets
    uri1 = file_storage_client.upload_file(
        bucket=bucket1, file_path=sample_file_path, storage_type="local"
    )
    uri2 = file_storage_client.upload_file(
        bucket=bucket2, file_path=sample_file_path, storage_type="local"
    )

    file_data1, metadata1 = file_storage_client.storage_system.get_file(uri1)
    file_data2, metadata2 = file_storage_client.storage_system.get_file(uri2)

    # Verify that file hashes are the same for the same content
    file_hash1 = file_storage_client.storage_system._calculate_file_hash(file_data1)
    file_hash2 = file_storage_client.storage_system._calculate_file_hash(file_data2)

    assert file_hash1 == metadata1.file_hash
    assert file_hash2 == metadata2.file_hash
    assert file_hash1 == file_hash2


def test_file_download_from_different_buckets(
    file_storage_client, sample_file_path, temp_storage_path
):
    bucket1 = "bucket1"
    bucket2 = "bucket2"

    # Upload the file to both buckets
    uri1 = file_storage_client.upload_file(
        bucket=bucket1, file_path=sample_file_path, storage_type="local"
    )
    uri2 = file_storage_client.upload_file(
        bucket=bucket2, file_path=sample_file_path, storage_type="local"
    )

    # Download files to different locations
    download_path1 = os.path.join(temp_storage_path, "downloaded_bucket1.txt")
    download_path2 = os.path.join(temp_storage_path, "downloaded_bucket2.txt")

    file_storage_client.download_file(uri1, download_path1)
    file_storage_client.download_file(uri2, download_path2)

    # Verify contents of downloaded files
    assert open(download_path1, "rb").read() == b"Sample file content"
    assert open(download_path2, "rb").read() == b"Sample file content"


def test_delete_all_files_in_bucket(file_storage_client, sample_file_path):
    bucket1 = "bucket1"
    bucket2 = "bucket2"

    # Upload files to both buckets
    file_storage_client.upload_file(
        bucket=bucket1, file_path=sample_file_path, storage_type="local"
    )
    file_storage_client.upload_file(
        bucket=bucket2, file_path=sample_file_path, storage_type="local"
    )

    # Delete all files in bucket1
    for file in file_storage_client.list_files(bucket=bucket1):
        file_storage_client.delete_file(file.uri)

    # Verify bucket1 is empty
    assert len(file_storage_client.list_files(bucket=bucket1)) == 0

    # Verify bucket2 still has files
    assert len(file_storage_client.list_files(bucket=bucket2)) == 1


def test_simple_distributed_storage_save_file(
    distributed_storage_backend, sample_file_data, temp_storage_path
):
    bucket = "test-bucket"
    file_id = "test_file"
    file_path = distributed_storage_backend.save(bucket, file_id, sample_file_data)

    expected_path = os.path.join(
        temp_storage_path,
        bucket,
        f"{file_id}_{hashlib.md5('127.0.0.1:8000'.encode()).hexdigest()}",
    )
    assert file_path == f"distributed://127.0.0.1:8000/{bucket}/{file_id}"
    assert os.path.exists(expected_path)


def test_simple_distributed_storage_load_file_local(
    distributed_storage_backend, sample_file_data
):
    bucket = "test-bucket"
    file_id = "test_file"
    distributed_storage_backend.save(bucket, file_id, sample_file_data)

    metadata = FileMetadata(
        file_id=file_id,
        bucket=bucket,
        file_name="test.txt",
        file_size=len(sample_file_data.getvalue()),
        storage_type="distributed",
        storage_path=f"distributed://127.0.0.1:8000/{bucket}/{file_id}",
        uri=f"distributed://127.0.0.1:8000/{bucket}/{file_id}",
        custom_metadata={},
        file_hash="hash",
    )

    file_data = distributed_storage_backend.load(metadata)
    assert file_data.read() == b"Sample file content for distributed storage"


@mock.patch("requests.get")
def test_simple_distributed_storage_load_file_remote(
    mock_get, distributed_storage_backend, sample_file_data
):
    bucket = "test-bucket"
    file_id = "test_file"
    remote_node_address = "127.0.0.2:8000"

    # Mock the response from remote node
    mock_response = mock.Mock()
    mock_response.iter_content = mock.Mock(
        return_value=iter([b"Sample file content for distributed storage"])
    )
    mock_response.raise_for_status = mock.Mock(return_value=None)
    mock_get.return_value = mock_response

    metadata = FileMetadata(
        file_id=file_id,
        bucket=bucket,
        file_name="test.txt",
        file_size=len(sample_file_data.getvalue()),
        storage_type="distributed",
        storage_path=f"distributed://{remote_node_address}/{bucket}/{file_id}",
        uri=f"distributed://{remote_node_address}/{bucket}/{file_id}",
        custom_metadata={},
        file_hash="hash",
    )

    file_data = distributed_storage_backend.load(metadata)
    assert file_data.read() == b"Sample file content for distributed storage"
    mock_get.assert_called_once_with(
        f"http://{remote_node_address}/api/v2/serve/file/files/{bucket}/{file_id}",
        stream=True,
        timeout=360,
    )


def test_simple_distributed_storage_delete_file_local(
    distributed_storage_backend, sample_file_data, temp_storage_path
):
    bucket = "test-bucket"
    file_id = "test_file"
    distributed_storage_backend.save(bucket, file_id, sample_file_data)

    metadata = FileMetadata(
        file_id=file_id,
        bucket=bucket,
        file_name="test.txt",
        file_size=len(sample_file_data.getvalue()),
        storage_type="distributed",
        storage_path=f"distributed://127.0.0.1:8000/{bucket}/{file_id}",
        uri=f"distributed://127.0.0.1:8000/{bucket}/{file_id}",
        custom_metadata={},
        file_hash="hash",
    )

    result = distributed_storage_backend.delete(metadata)
    file_path = os.path.join(
        temp_storage_path,
        bucket,
        f"{file_id}_{hashlib.md5('127.0.0.1:8000'.encode()).hexdigest()}",
    )
    assert result is True
    assert not os.path.exists(file_path)


@mock.patch("requests.delete")
def test_simple_distributed_storage_delete_file_remote(
    mock_delete, distributed_storage_backend, sample_file_data
):
    bucket = "test-bucket"
    file_id = "test_file"
    remote_node_address = "127.0.0.2:8000"

    mock_response = mock.Mock()
    mock_response.raise_for_status = mock.Mock(return_value=None)
    mock_delete.return_value = mock_response

    metadata = FileMetadata(
        file_id=file_id,
        bucket=bucket,
        file_name="test.txt",
        file_size=len(sample_file_data.getvalue()),
        storage_type="distributed",
        storage_path=f"distributed://{remote_node_address}/{bucket}/{file_id}",
        uri=f"distributed://{remote_node_address}/{bucket}/{file_id}",
        custom_metadata={},
        file_hash="hash",
    )

    result = distributed_storage_backend.delete(metadata)
    assert result is True
    mock_delete.assert_called_once_with(
        f"http://{remote_node_address}/api/v2/serve/file/files/{bucket}/{file_id}",
        timeout=360,
    )
