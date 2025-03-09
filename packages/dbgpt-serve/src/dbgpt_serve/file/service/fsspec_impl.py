import io
import os
import tempfile
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from fsspec import AbstractFileSystem
from fsspec.utils import stringify_path

from dbgpt.core.interface.file import (
    FileMetadata,
    FileStorageClient,
    FileStorageURI,
)


class DBGPTFileSystem(AbstractFileSystem):
    """Interface to files in DBGPTFileStorage

    Parameters
    ----------
    client : FileStorageClient
        The underlying FileStorageClient to use
    bucket : str
        Default bucket to use
    storage_type : str
        Default storage type to use (e.g., "local", "distributed")
    auto_mkdir : bool
        Whether to automatically create parent directories when needed
    """

    protocol = "dbgpt-fs"
    root_marker = "/"

    def __init__(
        self,
        client: Optional[FileStorageClient] = None,
        bucket: str = "default",
        storage_type: str = "local",
        auto_mkdir: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.client = client or self._create_default_client()
        self.bucket = bucket
        self.storage_type = storage_type
        self.auto_mkdir = auto_mkdir
        self._temp_files = {}  # 用于跟踪临时文件

    @staticmethod
    def _create_default_client():
        """Create a default FileStorageClient."""

        return FileStorageClient()

    @property
    def fsid(self):
        return f"dbgpt-{self.bucket}"

    def _parse_path(self, path: str) -> Tuple[str, str, str]:
        """Parse a path into storage_type, bucket, and file_id.

        Returns:
            Tuple containing (storage_type, bucket, file_id)
        """
        path = stringify_path(path)

        # Handle full URI format
        if path.startswith(f"{self.protocol}://"):
            try:
                uri = FileStorageURI.parse(path)
                return uri.storage_type, uri.bucket, uri.file_id
            except Exception as e:
                raise ValueError(f"Failed to parse URI {path}: {str(e)}")

        # Handle local files
        if FileStorageURI.is_local_file(path):
            # Treat as a local file reference
            file_name = os.path.basename(path)
            return "local", self.bucket, file_name

        # Handle simplified path format (bucket/file_id)
        path = self._strip_protocol(path)
        if path.startswith("/"):
            path = path[1:]

        parts = path.split("/", 1)
        if len(parts) == 1:
            # No bucket specified, use default bucket and storage type
            return self.storage_type, self.bucket, parts[0]
        else:
            # Bucket specified, use default storage type
            return self.storage_type, parts[0], parts[1]

    def _strip_protocol(self, path):
        """Remove protocol from path."""
        path = stringify_path(path)
        if path.startswith(f"{self.protocol}://"):
            # Get everything after the protocol and netloc
            parsed = urlparse(path)
            return parsed.path
        return path

    def _is_uri(self, path):
        """Check if path is a full URI."""
        return path.startswith(f"{self.protocol}://")

    def ls(self, path, detail=False, **kwargs):
        """List objects at path.

        Parameters
        ----------
        path : str
            Location to list (bucket or bucket/prefix)
        detail : bool
            If True, return a list of dictionaries, otherwise just the paths

        Returns
        -------
        List of file names or list of file details
        """
        storage_type, bucket, prefix = self._parse_path(path)

        # If the path points to a specific file_id, check if it exists
        if prefix and "/" not in prefix:
            metadata = self.client.storage_system.get_file_metadata(bucket, prefix)
            if metadata:
                if detail:
                    return [self._metadata_to_detail(metadata)]
                else:
                    return [f"{bucket}/{metadata.file_id}"]

        # List files in the bucket
        filters = {}
        if prefix:
            # Try to filter by prefix (assuming custom implementation in backend)
            filters["file_id_prefix"] = prefix

        files = self.client.list_files(bucket, filters)

        if detail:
            return [self._metadata_to_detail(file) for file in files]
        else:
            return [f"{bucket}/{file.file_id}" for file in files]

    def _metadata_to_detail(self, metadata: FileMetadata) -> Dict:
        """Convert FileMetadata to a detail dict expected by fsspec."""
        return {
            "name": f"{metadata.bucket}/{metadata.file_id}",
            "size": metadata.file_size,
            "type": "file",
            "created": None,  # No creation time in FileMetadata
            "custom_metadata": metadata.custom_metadata,
            "file_name": metadata.file_name,
        }

    def info(self, path, **kwargs):
        """Get metadata about a single file."""
        storage_type, bucket, file_id = self._parse_path(path)
        metadata = self.client.storage_system.get_file_metadata(bucket, file_id)
        if metadata:
            return self._metadata_to_detail(metadata)
        raise FileNotFoundError(f"File {path} not found")

    def _open(
        self,
        path,
        mode="rb",
        block_size=None,
        autocommit=True,
        cache_options=None,
        **kwargs,
    ):
        """Open a file for reading or writing."""
        if mode not in ("rb", "wb", "ab"):
            raise ValueError(f"Unsupported mode: {mode}")

        return DBGPTFile(
            self,
            path,
            mode,
            autocommit=autocommit,
            block_size=block_size,
            cache_options=cache_options,
            **kwargs,
        )

    def cp_file(self, path1, path2, **kwargs):
        """Copy file within the file system."""
        # Read content from source
        with self.open(path1, "rb") as f1:
            content = f1.read()

        # Write content to destination
        with self.open(path2, "wb") as f2:
            f2.write(content)

    def rm_file(self, path):
        """Remove a file."""
        storage_type, bucket, file_id = self._parse_path(path)
        if not self.client.delete_file_by_id(bucket, file_id):
            raise FileNotFoundError(f"File {path} not found")

    def rm(self, path, recursive=False, maxdepth=None):
        """Remove a file or a directory."""
        if isinstance(path, list):
            for p in path:
                self.rm(p, recursive, maxdepth)
            return

        storage_type, bucket, file_id = self._parse_path(path)

        if "/" in file_id:
            if not recursive:
                raise ValueError("Cannot delete directory without recursive=True")

            # This is a directory-like path - delete all matching files
            files = self.ls(path)
            for file_path in files:
                self.rm_file(file_path)
        else:
            # This is a single file
            self.rm_file(path)

    def exists(self, path):
        """Check if file exists."""
        storage_type, bucket, file_id = self._parse_path(path)
        try:
            metadata = self.client.storage_system.get_file_metadata(bucket, file_id)
            return metadata is not None
        except Exception as _e:
            return False

    def created(self, path):
        """Get creation time - not supported."""
        raise NotImplementedError("created() is not supported by DBGPTFileSystem")

    def modified(self, path):
        """Get modification time - not supported."""
        raise NotImplementedError("modified() is not supported by DBGPTFileSystem")

    def mkdir(self, path, create_parents=True, **kwargs):
        """Create directory - not needed for DBGPTFileSystem."""
        # No-op since we don't have directories
        pass

    def makedirs(self, path, exist_ok=True):
        """Create directory and parents - not needed for DBGPTFileSystem."""
        # No-op since we don't have directories
        pass

    def isdir(self, path):
        """Check if path is a directory - always False in this filesystem."""
        # We don't have real directories
        return False

    def isfile(self, path):
        """Check if path is a file."""
        return self.exists(path)


class DBGPTFile(io.IOBase):
    """File-like interface for DBGPTFileSystem."""

    def __init__(
        self,
        fs: DBGPTFileSystem,
        path: str,
        mode: str = "rb",
        autocommit: bool = True,
        block_size: Optional[int] = None,
        cache_options: Optional[Dict] = None,
        **kwargs,
    ):
        self.fs = fs
        self.path = path
        self.mode = mode
        self.autocommit = autocommit

        storage_type, bucket, file_id = fs._parse_path(path)
        self.storage_type = storage_type
        self.bucket = bucket
        self.file_id = file_id
        self.file_name = kwargs.get("file_name", file_id)
        self.custom_metadata = kwargs.get("custom_metadata", {})

        # File handle
        self.buffer = None
        self._closed = False

        # For write modes
        self.temp_file = None

        self._open()

    def _open(self):
        """Open the file depending on mode."""
        if self.buffer is not None:
            self.buffer.close()

        if "r" in self.mode:
            try:
                # Reading mode
                file_data, metadata = self.fs.client.get_file_by_id(
                    self.bucket, self.file_id
                )
                self.buffer = file_data
                self.metadata = metadata
            except FileNotFoundError:
                raise FileNotFoundError(f"File {self.path} not found")
        else:
            # Writing mode
            self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+b")
            self.buffer = self.temp_file

    def read(self, size=-1):
        """Read from the file."""
        if "r" not in self.mode:
            raise ValueError("File not open for reading")
        return self.buffer.read(size)

    def write(self, data):
        """Write to the file."""
        if "w" not in self.mode and "a" not in self.mode:
            raise ValueError("File not open for writing")
        return self.buffer.write(data)

    def close(self):
        """Close the file and commit changes if writing."""
        if self._closed:
            return

        if self.buffer:
            self.buffer.close()

        if "w" in self.mode or "a" in self.mode:
            if self.autocommit:
                self.commit()

        self._closed = True

    def commit(self):
        """Commit the file by saving it to the storage system."""
        if not self.temp_file:
            return

        # Reopen the temp file for reading
        with open(self.temp_file.name, "rb") as f:
            # Save the file to the storage system
            uri = self.fs.client.save_file(
                self.bucket, self.file_name, f, self.storage_type, self.custom_metadata
            )

        # Parse the uri to get the file_id for future reference
        parsed_uri = FileStorageURI.parse(uri)
        self.file_id = parsed_uri.file_id

        # Clean up the temp file
        os.unlink(self.temp_file.name)
        self.temp_file = None

    def discard(self):
        """Discard changes by deleting the temp file."""
        if self.temp_file:
            os.unlink(self.temp_file.name)
            self.temp_file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def closed(self):
        return self._closed
