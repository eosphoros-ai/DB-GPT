"""File storage interface."""

import dataclasses
import hashlib
import io
import logging
import os
import uuid
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.util.tracer import root_tracer, trace

from ...util import BaseParameters, RegisterParameters
from .storage import (
    InMemoryStorage,
    QuerySpec,
    ResourceIdentifier,
    StorageError,
    StorageInterface,
    StorageItem,
)

logger = logging.getLogger(__name__)
_SCHEMA = "dbgpt-fs"


@dataclasses.dataclass
class FileMetadataIdentifier(ResourceIdentifier):
    """File metadata identifier."""

    file_id: str
    bucket: str

    def to_dict(self) -> Dict:
        """Convert the identifier to a dictionary."""
        return {"file_id": self.file_id, "bucket": self.bucket}

    @property
    def str_identifier(self) -> str:
        """Get the string identifier.

        Returns:
            str: The string identifier
        """
        return f"{self.bucket}/{self.file_id}"


@dataclasses.dataclass
class FileMetadata(StorageItem):
    """File metadata for storage."""

    file_id: str
    bucket: str
    file_name: str
    file_size: int
    storage_type: str
    storage_path: str
    uri: str
    custom_metadata: Dict[str, Any]
    file_hash: str
    user_name: Optional[str] = None
    sys_code: Optional[str] = None
    _identifier: FileMetadataIdentifier = dataclasses.field(init=False)

    def __post_init__(self):
        """Post init method."""
        self._identifier = FileMetadataIdentifier(
            file_id=self.file_id, bucket=self.bucket
        )
        custom_metadata = self.custom_metadata or {}
        if not self.user_name:
            self.user_name = custom_metadata.get("user_name")
        if not self.sys_code:
            self.sys_code = custom_metadata.get("sys_code")

    @property
    def identifier(self) -> ResourceIdentifier:
        """Get the resource identifier."""
        return self._identifier

    def merge(self, other: "StorageItem") -> None:
        """Merge the metadata with another item."""
        if not isinstance(other, FileMetadata):
            raise StorageError("Cannot merge different types of items")
        self._from_object(other)

    def to_dict(self) -> Dict:
        """Convert the metadata to a dictionary."""
        return {
            "file_id": self.file_id,
            "bucket": self.bucket,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "storage_type": self.storage_type,
            "storage_path": self.storage_path,
            "uri": self.uri,
            "custom_metadata": self.custom_metadata,
            "file_hash": self.file_hash,
        }

    def _from_object(self, obj: "FileMetadata") -> None:
        self.file_id = obj.file_id
        self.bucket = obj.bucket
        self.file_name = obj.file_name
        self.file_size = obj.file_size
        self.storage_type = obj.storage_type
        self.storage_path = obj.storage_path
        self.uri = obj.uri
        self.custom_metadata = obj.custom_metadata
        self.file_hash = obj.file_hash
        self._identifier = obj._identifier


@dataclasses.dataclass
class StorageBackendConfig(BaseParameters, RegisterParameters):
    """Storage backend configuration"""

    __type__ = "___storage_backend_config___"
    __cfg_type__ = "utils"

    def create_storage(self) -> "StorageBackend":
        """Create the storage"""
        raise NotImplementedError()


class FileStorageURI:
    """File storage URI."""

    def __init__(
        self,
        storage_type: str,
        bucket: str,
        file_id: str,
        version: Optional[str] = None,
        custom_params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the file storage URI."""
        self.scheme = _SCHEMA
        self.storage_type = storage_type
        self.bucket = bucket
        self.file_id = file_id
        self.version = version
        self.custom_params = custom_params or {}

    @classmethod
    def is_local_file(cls, uri: str) -> bool:
        """Check if the URI is local."""
        parsed = urlparse(uri)
        if not parsed.scheme or parsed.scheme == "file":
            return True
        return False

    @classmethod
    def parse(cls, uri: str) -> "FileStorageURI":
        """Parse the URI string."""
        parsed = urlparse(uri)
        if parsed.scheme != _SCHEMA:
            raise ValueError(f"Invalid URI scheme. Must be '{_SCHEMA}'")
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError("Invalid URI path. Must contain bucket and file ID")
        storage_type = parsed.netloc
        bucket = path_parts[0]
        file_id = path_parts[1]
        version = path_parts[2] if len(path_parts) > 2 else None
        custom_params = parse_qs(parsed.query)
        return cls(storage_type, bucket, file_id, version, custom_params)

    def __str__(self) -> str:
        """Get the string representation of the URI."""
        base_uri = f"{self.scheme}://{self.storage_type}/{self.bucket}/{self.file_id}"
        if self.version:
            base_uri += f"/{self.version}"
        if self.custom_params:
            query_string = urlencode(self.custom_params, doseq=True)
            base_uri += f"?{query_string}"
        return base_uri


class StorageBackend(ABC):
    """Storage backend interface."""

    storage_type: str = "__base__"

    @abstractmethod
    def save(self, bucket: str, file_id: str, file_data: BinaryIO) -> str:
        """Save the file data to the storage backend.

        Args:
            bucket (str): The bucket name
            file_id (str): The file ID
            file_data (BinaryIO): The file data

        Returns:
            str: The storage path
        """

    @abstractmethod
    def load(self, fm: FileMetadata) -> BinaryIO:
        """Load the file data from the storage backend.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            BinaryIO: The file data
        """

    @abstractmethod
    def delete(self, fm: FileMetadata) -> bool:
        """Delete the file data from the storage backend.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            bool: True if the file was deleted, False otherwise
        """

    @property
    @abstractmethod
    def save_chunk_size(self) -> int:
        """Get the save chunk size.

        Returns:
            int: The save chunk size
        """


class LocalFileStorage(StorageBackend):
    """Local file storage backend."""

    storage_type: str = "local"

    def __init__(self, base_path: str, save_chunk_size: int = 1024 * 1024):
        """Initialize the local file storage backend."""
        self.base_path = base_path
        self._save_chunk_size = save_chunk_size
        os.makedirs(self.base_path, exist_ok=True)

    @property
    def save_chunk_size(self) -> int:
        """Get the save chunk size."""
        return self._save_chunk_size

    def save(self, bucket: str, file_id: str, file_data: BinaryIO) -> str:
        """Save the file data to the local storage backend."""
        bucket_path = os.path.join(self.base_path, bucket)
        os.makedirs(bucket_path, exist_ok=True)
        file_path = os.path.join(bucket_path, file_id)
        with open(file_path, "wb") as f:
            while True:
                chunk = file_data.read(self.save_chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        return file_path

    def load(self, fm: FileMetadata) -> BinaryIO:
        """Load the file data from the local storage backend."""
        bucket_path = os.path.join(self.base_path, fm.bucket)
        file_path = os.path.join(bucket_path, fm.file_id)
        return open(file_path, "rb")  # noqa: SIM115

    def delete(self, fm: FileMetadata) -> bool:
        """Delete the file data from the local storage backend."""
        bucket_path = os.path.join(self.base_path, fm.bucket)
        file_path = os.path.join(bucket_path, fm.file_id)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False


def calculate_file_hash(file_data: BinaryIO, buffer_size: int) -> str:
    """Calculate the MD5 hash of the file data."""
    hasher = hashlib.md5()
    file_data.seek(0)
    while chunk := file_data.read(buffer_size):
        hasher.update(chunk)
    file_data.seek(0)
    return hasher.hexdigest()


class FileStorageSystem:
    """File storage system."""

    def __init__(
        self,
        storage_backends: Dict[str, StorageBackend],
        metadata_storage: Optional[StorageInterface[FileMetadata, Any]] = None,
        check_hash: bool = True,
    ):
        """Initialize the file storage system."""
        metadata_storage = metadata_storage or InMemoryStorage()
        self.storage_backends = storage_backends
        self.metadata_storage = metadata_storage
        self.check_hash = check_hash
        self._save_chunk_size = min(
            backend.save_chunk_size for backend in storage_backends.values()
        )

    def _calculate_file_hash(self, file_data: BinaryIO) -> str:
        """Calculate the MD5 hash of the file data."""
        if not self.check_hash:
            return "-1"
        return calculate_file_hash(file_data, self._save_chunk_size)

    @trace("file_storage_system.save_file")
    def save_file(
        self,
        bucket: str,
        file_name: str,
        file_data: BinaryIO,
        storage_type: str,
        custom_metadata: Optional[Dict[str, Any]] = None,
        file_id: Optional[str] = None,
    ) -> str:
        """Save the file data to the storage backend."""
        file_id = str(uuid.uuid4()) if not file_id else file_id
        backend = self.storage_backends.get(storage_type)
        if not backend:
            raise ValueError(f"Unsupported storage type: {storage_type}")

        with root_tracer.start_span(
            "file_storage_system.save_file.backend_save",
            metadata={
                "bucket": bucket,
                "file_id": file_id,
                "file_name": file_name,
                "storage_type": storage_type,
            },
        ):
            storage_path = backend.save(bucket, file_id, file_data)
        file_data.seek(0, 2)  # Move to the end of the file
        file_size = file_data.tell()  # Get the file size
        file_data.seek(0)  # Reset file pointer

        # filter None value
        custom_metadata = (
            {k: v for k, v in custom_metadata.items() if v is not None}
            if custom_metadata
            else {}
        )

        with root_tracer.start_span(
            "file_storage_system.save_file.calculate_hash",
        ):
            file_hash = self._calculate_file_hash(file_data)
        uri = FileStorageURI(
            storage_type, bucket, file_id, custom_params=custom_metadata
        )

        metadata = FileMetadata(
            file_id=file_id,
            bucket=bucket,
            file_name=file_name,
            file_size=file_size,
            storage_type=storage_type,
            storage_path=storage_path,
            uri=str(uri),
            custom_metadata=custom_metadata,
            file_hash=file_hash,
        )

        self.metadata_storage.save(metadata)
        return str(uri)

    @trace("file_storage_system.get_file")
    def get_file(self, uri: str) -> Tuple[BinaryIO, FileMetadata]:
        """Get the file data from the storage backend."""
        if FileStorageURI.is_local_file(uri):
            local_file_name = uri.split("/")[-1]
            if not os.path.exists(uri):
                raise FileNotFoundError(f"File not found: {uri}")

            dummy_metadata = FileMetadata(
                file_id=local_file_name,
                bucket="dummy_bucket",
                file_name=local_file_name,
                file_size=-1,
                storage_type="local",
                storage_path=uri,
                uri=uri,
                custom_metadata={},
                file_hash="",
            )
            logger.info(f"Reading local file: {uri}")
            return open(uri, "rb"), dummy_metadata  # noqa: SIM115

        parsed_uri = FileStorageURI.parse(uri)
        metadata = self.metadata_storage.load(
            FileMetadataIdentifier(
                file_id=parsed_uri.file_id, bucket=parsed_uri.bucket
            ),
            FileMetadata,
        )
        if not metadata:
            raise FileNotFoundError(f"No metadata found for URI: {uri}")

        backend = self.storage_backends.get(metadata.storage_type)
        if not backend:
            raise ValueError(f"Unsupported storage type: {metadata.storage_type}")

        with root_tracer.start_span(
            "file_storage_system.get_file.backend_load",
            metadata={
                "bucket": metadata.bucket,
                "file_id": metadata.file_id,
                "file_name": metadata.file_name,
                "storage_type": metadata.storage_type,
            },
        ):
            file_data = backend.load(metadata)

        with root_tracer.start_span(
            "file_storage_system.get_file.verify_hash",
        ):
            calculated_hash = self._calculate_file_hash(file_data)
        if calculated_hash != "-1" and calculated_hash != metadata.file_hash:
            raise ValueError("File integrity check failed. Hash mismatch.")

        return file_data, metadata

    def get_file_metadata(self, bucket: str, file_id: str) -> Optional[FileMetadata]:
        """Get the file metadata.

        Args:
            bucket (str): The bucket name
            file_id (str): The file ID

        Returns:
            Optional[FileMetadata]: The file metadata
        """
        fid = FileMetadataIdentifier(file_id=file_id, bucket=bucket)
        return self.metadata_storage.load(fid, FileMetadata)

    def get_file_metadata_by_uri(self, uri: str) -> Optional[FileMetadata]:
        """Get the file metadata by URI.

        Args:
            uri (str): The file URI

        Returns:
            Optional[FileMetadata]: The file metadata
        """
        parsed_uri = FileStorageURI.parse(uri)
        return self.get_file_metadata(parsed_uri.bucket, parsed_uri.file_id)

    def delete_file(self, uri: str) -> bool:
        """Delete the file data from the storage backend.

        Args:
            uri (str): The file URI

        Returns:
            bool: True if the file was deleted, False otherwise
        """
        parsed_uri = FileStorageURI.parse(uri)
        fid = FileMetadataIdentifier(
            file_id=parsed_uri.file_id, bucket=parsed_uri.bucket
        )
        metadata = self.metadata_storage.load(fid, FileMetadata)
        if not metadata:
            return False

        backend = self.storage_backends.get(metadata.storage_type)
        if not backend:
            raise ValueError(f"Unsupported storage type: {metadata.storage_type}")

        if backend.delete(metadata):
            try:
                self.metadata_storage.delete(fid)
                return True
            except Exception:
                # If the metadata deletion fails, log the error and return False
                return False
        return False

    def list_files(
        self, bucket: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[FileMetadata]:
        """List the files in the bucket."""
        filters = filters or {}
        filters["bucket"] = bucket
        return self.metadata_storage.query(QuerySpec(conditions=filters), FileMetadata)


class FileStorageClient(BaseComponent):
    """File storage client component."""

    name = ComponentType.FILE_STORAGE_CLIENT.value

    def __init__(
        self,
        system_app: Optional[SystemApp] = None,
        storage_system: Optional[FileStorageSystem] = None,
        save_chunk_size: int = 1024 * 1024,
        default_storage_type: Optional[str] = None,
    ):
        """Initialize the file storage client."""
        super().__init__(system_app=system_app)
        if not storage_system:
            from pathlib import Path

            base_path = Path.home() / ".cache" / "dbgpt" / "files"
            storage_system = FileStorageSystem(
                {
                    LocalFileStorage.storage_type: LocalFileStorage(
                        base_path=str(base_path)
                    )
                }
            )
        if not default_storage_type:
            if storage_system and storage_system.storage_backends:
                default_storage_type = list(storage_system.storage_backends.keys())[0]

        self.system_app = system_app
        self._storage_system = storage_system
        self.save_chunk_size = save_chunk_size
        self.default_storage_type = default_storage_type

    def init_app(self, system_app: SystemApp):
        """Initialize the application."""
        self.system_app = system_app

    @property
    def storage_system(self) -> FileStorageSystem:
        """Get the file storage system."""
        if not self._storage_system:
            raise ValueError("File storage system not initialized")
        return self._storage_system

    def upload_file(
        self,
        bucket: str,
        file_path: str,
        storage_type: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        file_id: Optional[str] = None,
    ) -> str:
        """Upload a file to the storage system.

        Args:
            bucket (str): The bucket name
            file_path (str): The file path
            storage_type (str): The storage type
            custom_metadata (Dict[str, Any], optional): Custom metadata. Defaults to
                None.
            file_id (str, optional): The file ID. Defaults to None. If not provided, a
                random UUID will be generated.

        Returns:
            str: The file URI
        """
        with open(file_path, "rb") as file:
            return self.save_file(
                bucket,
                os.path.basename(file_path),
                file,
                storage_type,
                custom_metadata,
                file_id,
            )

    def save_file(
        self,
        bucket: str,
        file_name: str,
        file_data: BinaryIO,
        storage_type: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        file_id: Optional[str] = None,
    ) -> str:
        """Save the file data to the storage system.

        Args:
            bucket (str): The bucket name
            file_name (str): The file name
            file_data (BinaryIO): The file data
            storage_type (str): The storage type
            custom_metadata (Dict[str, Any], optional): Custom metadata. Defaults to
                None.
            file_id(str, optional): The file ID. Defaults to None. If not provided, a
                random UUID will be generated.

        Returns:
            str: The file URI
        """
        if not storage_type:
            storage_type = self.default_storage_type
        if not storage_type:
            raise ValueError("Storage type not provided")
        return self.storage_system.save_file(
            bucket, file_name, file_data, storage_type, custom_metadata, file_id
        )

    def download_file(
        self,
        uri: str,
        dest_path: Optional[str] = None,
        dest_dir: Optional[str] = None,
        cache: bool = True,
    ) -> Tuple[str, FileMetadata]:
        """Download a file from the storage system.

        If dest_path is provided, the file will be saved to that path.
        If dest_dir is provided, the file will be saved to that directory with
        file ID and extension.

        If neither dest_path nor dest_dir is provided, the file will be saved to the
        system temp directory.

        Args:
            uri (str): The file URI
            dest_path (str, optional): The destination path. Defaults to None.
            dest_dir (str, optional): The destination directory. Defaults to None.
            cache (bool, optional): Whether to cache the file. Defaults to True.

        Raises:
            FileNotFoundError: If the file is not found
        """
        file_metadata = self.storage_system.get_file_metadata_by_uri(uri)
        if not file_metadata:
            raise FileNotFoundError(f"File not found: {uri}")

        extension = os.path.splitext(file_metadata.file_name)[1]
        if dest_path:
            target_path = dest_path
        elif dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
            target_path = os.path.join(dest_dir, file_metadata.file_id + extension)
        else:
            from pathlib import Path

            # Write to system temp directory
            base_path = str(Path.home() / ".cache" / "dbgpt" / "files")
            os.makedirs(base_path, exist_ok=True)
            target_path = os.path.join(base_path, file_metadata.file_id + extension)
        file_hash = file_metadata.file_hash
        if os.path.exists(target_path) and cache:
            logger.debug(f"File {target_path} already exists, begin hash check")
            with open(target_path, "rb") as f:
                if file_hash == calculate_file_hash(f, self.save_chunk_size):
                    logger.info(f"File {uri} already exists at {target_path}")
                    return target_path, file_metadata
        logger.info(f"Downloading file {uri} to {target_path}")
        file_data, _ = self.storage_system.get_file(uri)

        with open(target_path, "wb") as f:
            while True:
                chunk = file_data.read(self.save_chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        return target_path, file_metadata

    def get_file(self, uri: str) -> Tuple[BinaryIO, FileMetadata]:
        """Get the file data from the storage system.

        Args:
            uri (str): The file URI

        Returns:
            Tuple[BinaryIO, FileMetadata]: The file data and metadata
        """
        return self.storage_system.get_file(uri)

    def get_file_by_id(
        self, bucket: str, file_id: str
    ) -> Tuple[BinaryIO, FileMetadata]:
        """Get the file data from the storage system by ID.

        Args:
            bucket (str): The bucket name
            file_id (str): The file ID

        Returns:
            Tuple[BinaryIO, FileMetadata]: The file data and metadata
        """
        metadata = self.storage_system.get_file_metadata(bucket, file_id)
        if not metadata:
            raise FileNotFoundError(f"File {file_id} not found in bucket {bucket}")
        return self.get_file(metadata.uri)

    def delete_file(self, uri: str) -> bool:
        """Delete the file data from the storage system.

        Args:
            uri (str): The file URI

        Returns:
            bool: True if the file was deleted, False otherwise
        """
        return self.storage_system.delete_file(uri)

    def delete_file_by_id(self, bucket: str, file_id: str) -> bool:
        """Delete the file data from the storage system by ID.

        Args:
            bucket (str): The bucket name
            file_id (str): The file ID

        Returns:
            bool: True if the file was deleted, False otherwise
        """
        metadata = self.storage_system.get_file_metadata(bucket, file_id)
        if not metadata:
            raise FileNotFoundError(f"File {file_id} not found in bucket {bucket}")
        return self.delete_file(metadata.uri)

    def list_files(
        self, bucket: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[FileMetadata]:
        """List the files in the bucket.

        Args:
            bucket (str): The bucket name
            filters (Dict[str, Any], optional): Filters. Defaults to None.

        Returns:
            List[FileMetadata]: The list of file metadata
        """
        return self.storage_system.list_files(bucket, filters)


class SimpleDistributedStorage(StorageBackend):
    """Simple distributed storage backend."""

    storage_type: str = "distributed"

    def __init__(
        self,
        node_address: str,
        local_storage_path: str,
        save_chunk_size: int = 1024 * 1024,
        transfer_chunk_size: int = 1024 * 1024,
        transfer_timeout: int = 360,
        api_prefix: str = "/api/v2/serve/file/files",
    ):
        """Initialize the simple distributed storage backend."""
        self.node_address = node_address
        self.local_storage_path = local_storage_path
        os.makedirs(self.local_storage_path, exist_ok=True)
        self._save_chunk_size = save_chunk_size
        self._transfer_chunk_size = transfer_chunk_size
        self._transfer_timeout = transfer_timeout
        self._api_prefix = api_prefix

    @property
    def save_chunk_size(self) -> int:
        """Get the save chunk size."""
        return self._save_chunk_size

    def _get_file_path(self, bucket: str, file_id: str, node_address: str) -> str:
        node_id = hashlib.md5(node_address.encode()).hexdigest()
        return os.path.join(self.local_storage_path, bucket, f"{file_id}_{node_id}")

    def _parse_node_address(self, fm: FileMetadata) -> str:
        storage_path = fm.storage_path
        if not storage_path.startswith("distributed://"):
            raise ValueError("Invalid storage path")
        return storage_path.split("//")[1].split("/")[0]

    def save(self, bucket: str, file_id: str, file_data: BinaryIO) -> str:
        """Save the file data to the distributed storage backend.

        Just save the file locally.

        Args:
            bucket (str): The bucket name
            file_id (str): The file ID
            file_data (BinaryIO): The file data

        Returns:
            str: The storage path
        """
        file_path = self._get_file_path(bucket, file_id, self.node_address)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            while True:
                chunk = file_data.read(self.save_chunk_size)
                if not chunk:
                    break
                f.write(chunk)

        return f"distributed://{self.node_address}/{bucket}/{file_id}"

    def load(self, fm: FileMetadata) -> BinaryIO:
        """Load the file data from the distributed storage backend.

        If the file is stored on the local node, load it from the local storage.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            BinaryIO: The file data
        """
        file_id = fm.file_id
        bucket = fm.bucket
        node_address = self._parse_node_address(fm)
        file_path = self._get_file_path(bucket, file_id, node_address)

        # TODO: check if the file is cached in local storage
        if node_address == self.node_address:
            if os.path.exists(file_path):
                return open(file_path, "rb")  # noqa: SIM115
            else:
                raise FileNotFoundError(f"File {file_id} not found on the local node")
        else:
            response = requests.get(
                f"http://{node_address}{self._api_prefix}/{bucket}/{file_id}",
                timeout=self._transfer_timeout,
                stream=True,
            )
            response.raise_for_status()
            # TODO: cache the file in local storage
            return StreamedBytesIO(
                response.iter_content(chunk_size=self._transfer_chunk_size)
            )

    def delete(self, fm: FileMetadata) -> bool:
        """Delete the file data from the distributed storage backend.

        If the file is stored on the local node, delete it from the local storage.
        If the file is stored on a remote node, send a delete request to the remote
        node.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            bool: True if the file was deleted, False otherwise
        """
        file_id = fm.file_id
        bucket = fm.bucket
        node_address = self._parse_node_address(fm)
        file_path = self._get_file_path(bucket, file_id, node_address)
        if node_address == self.node_address:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        else:
            try:
                response = requests.delete(
                    f"http://{node_address}{self._api_prefix}/{bucket}/{file_id}",
                    timeout=self._transfer_timeout,
                )
                response.raise_for_status()
                return True
            except Exception:
                return False


class StreamedBytesIO(io.BytesIO):
    """A BytesIO subclass that can be used with streaming responses.

    Adapted from: https://gist.github.com/obskyr/b9d4b4223e7eaf4eedcd9defabb34f13
    """

    def __init__(self, request_iterator):
        """Initialize the StreamedBytesIO instance."""
        super().__init__()
        self._bytes = BytesIO()
        self._iterator = request_iterator

    def _load_all(self):
        self._bytes.seek(0, io.SEEK_END)
        for chunk in self._iterator:
            self._bytes.write(chunk)

    def _load_until(self, goal_position):
        current_position = self._bytes.seek(0, io.SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break

    def tell(self) -> int:
        """Get the current position."""
        return self._bytes.tell()

    def read(self, size: Optional[int] = None) -> bytes:
        """Read the data from the stream.

        Args:
            size (Optional[int], optional): The number of bytes to read. Defaults to
                None.

        Returns:
            bytes: The read data
        """
        left_off_at = self._bytes.tell()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            self._load_until(goal_position)

        self._bytes.seek(left_off_at)
        return self._bytes.read(size)

    def seek(self, position: int, whence: int = io.SEEK_SET):
        """Seek to a position in the stream.

        Args:
            position (int): The position
            whence (int, optional): The reference point. Defaults to io.SEEK

        Raises:
            ValueError: If the reference point is invalid
        """
        if whence == io.SEEK_END:
            self._load_all()
        else:
            self._bytes.seek(position, whence)

    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, ext_type, value, tb):
        """Exit the context manager."""
        self._bytes.close()
