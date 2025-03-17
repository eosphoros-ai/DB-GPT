"""Aliyun OSS storage backend."""

import hashlib
import io
import logging
import os
import random
import time
from typing import BinaryIO, Callable, Dict, Optional, Union

import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider

from dbgpt.core.interface.file import FileMetadata, StorageBackend

logger = logging.getLogger(__name__)


def does_bucket_exist(bucket):
    try:
        bucket.get_bucket_info()
    except oss2.exceptions.NoSuchBucket:
        return False
    except:
        raise
    return True


class AliyunOSSStorage(StorageBackend):
    """Aliyun OSS storage backend implementation."""

    storage_type: str = "oss"

    def __init__(
        self,
        endpoint: str,
        region: str,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        save_chunk_size: int = 1024 * 1024,
        use_environment_credentials: bool = False,
        fixed_bucket: Optional[str] = None,
        bucket_prefix: str = "dbgpt-fs-",
        bucket_mapper: Optional[Callable[[str], str]] = None,
        auto_create_bucket: bool = True,
    ):
        """Initialize the Aliyun OSS storage backend.

        Args:
            endpoint (str): OSS endpoint, e.g., "https://oss-cn-hangzhou.aliyuncs.com"
            region (str): OSS region, e.g., "cn-hangzhou"
            access_key_id (Optional[str], optional): Aliyun Access Key ID. Defaults to
                None.
            access_key_secret (Optional[str], optional): Aliyun Access Key Secret.
                Defaults to None.
            save_chunk_size (int, optional): Chunk size for saving files. Defaults to
                1024*1024 (1MB).
            use_environment_credentials (bool, optional): Whether to use credentials
                from environment variables. Defaults to False.
            fixed_bucket (Optional[str], optional): A fixed OSS bucket to use for all
                operations. If provided, all logical buckets will be mapped to this
                single bucket. Defaults to None.
            bucket_prefix (str, optional): Prefix for dynamically created buckets.
                Defaults to "dbgpt-fs-".
            bucket_mapper (Optional[Callable[[str], str]], optional): Custom function
                to map logical bucket names to actual OSS bucket names. Defaults to
                None.
            auto_create_bucket (bool, optional): Whether to automatically create
                buckets that don't exist. Defaults to True.
        """
        self.endpoint = endpoint
        self.region = region
        self._save_chunk_size = save_chunk_size
        self.fixed_bucket = fixed_bucket
        self.bucket_prefix = bucket_prefix
        self.custom_bucket_mapper = bucket_mapper
        self.auto_create_bucket = auto_create_bucket

        # Initialize OSS authentication
        if use_environment_credentials:
            # Check required environment variables
            required_env_vars = ["OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET"]
            for var in required_env_vars:
                if var not in os.environ:
                    raise ValueError(f"Environment variable {var} is not set.")
            self.auth = oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider())
        else:
            if not access_key_id or not access_key_secret:
                raise ValueError(
                    "Access key ID and secret are required when not using environment "
                    "credentials"
                )
            # Use provided credentials
            self.auth = oss2.Auth(access_key_id, access_key_secret)

        # Store buckets dict to avoid recreating bucket objects
        self._buckets: Dict[str, oss2.Bucket] = {}

        # Create fixed bucket if specified
        if self.fixed_bucket and self.auto_create_bucket:
            self._ensure_bucket_exists(self.fixed_bucket)

    @property
    def save_chunk_size(self) -> int:
        """Get the save chunk size."""
        return self._save_chunk_size

    def _map_bucket_name(self, logical_bucket: str) -> str:
        """Map logical bucket name to actual OSS bucket name.

        Args:
            logical_bucket (str): Logical bucket name used by the application

        Returns:
            str: Actual OSS bucket name to use
        """
        # 1. If using a fixed bucket, always return that
        if self.fixed_bucket:
            return self.fixed_bucket

        # 2. If a custom mapper is provided, use that
        if self.custom_bucket_mapper:
            return self.custom_bucket_mapper(logical_bucket)

        # 3. Otherwise, use a hash-based approach to generate a unique but
        # deterministic name
        # This avoids bucket name conflicts while maintaining consistency
        bucket_hash = hashlib.md5(logical_bucket.encode()).hexdigest()[:8]
        return f"{self.bucket_prefix}{bucket_hash}-{logical_bucket}"

    def _generate_dynamic_bucket_name(self) -> str:
        """Generate a unique bucket name for dynamic creation.

        Returns:
            str: A unique bucket name
        """
        # Using timestamp + random number to ensure uniqueness
        timestamp = int(time.time())
        random_number = random.randint(0, 9999)
        return f"{self.bucket_prefix}{timestamp}-{random_number}"

    def _ensure_bucket_exists(self, bucket_name: str) -> bool:
        """Ensure the bucket exists, create it if needed and if auto_create_bucket is
        True.

        Args:
            bucket_name (str): Bucket name

        Returns:
            bool: True if the bucket exists or was created, False otherwise
        """
        bucket = oss2.Bucket(self.auth, self.endpoint, bucket_name, region=self.region)

        try:
            if does_bucket_exist(bucket):
                return True

            if not self.auto_create_bucket:
                logger.warning(
                    f"Bucket {bucket_name} does not exist and auto_create_bucket is "
                    f"False"
                )
                return False

            logger.info(f"Creating bucket {bucket_name}")
            bucket.create_bucket(oss2.models.BUCKET_ACL_PRIVATE)
            return True
        except oss2.exceptions.ServerError as e:
            # Handle the case where bucket name is already taken by someone else
            if e.status == 409 and "BucketAlreadyExists" in str(e):
                logger.warning(
                    f"Bucket name {bucket_name} already exists and is owned by "
                    "someone else"
                )
                return False
            raise
        except oss2.exceptions.OssError as e:
            logger.error(f"Failed to create or check bucket {bucket_name}: {e}")
            raise

    def _get_bucket(self, logical_bucket: str) -> Union[oss2.Bucket, None]:
        """Get or create an OSS bucket object for the given logical bucket.

        Args:
            logical_bucket (str): Logical bucket name

        Returns:
            Union[oss2.Bucket, None]: Bucket object or None if bucket creation failed
        """
        # Get the actual OSS bucket name
        actual_bucket_name = self._map_bucket_name(logical_bucket)

        # Check if we've already cached this bucket
        if actual_bucket_name in self._buckets:
            return self._buckets[actual_bucket_name]

        # Try to ensure the mapped bucket exists
        if self._ensure_bucket_exists(actual_bucket_name):
            # Cache and return the bucket
            self._buckets[actual_bucket_name] = oss2.Bucket(
                self.auth, self.endpoint, actual_bucket_name, region=self.region
            )
            return self._buckets[actual_bucket_name]

        # If we get here, the bucket doesn't exist and couldn't be created
        # Try to create a dynamic bucket if we're not using a fixed bucket
        if not self.fixed_bucket and self.auto_create_bucket:
            # Generate a new unique bucket name
            dynamic_bucket = self._generate_dynamic_bucket_name()
            logger.info(
                f"Attempting to create dynamic bucket {dynamic_bucket} for logical "
                f"bucket {logical_bucket}"
            )

            if self._ensure_bucket_exists(dynamic_bucket):
                self._buckets[actual_bucket_name] = oss2.Bucket(
                    self.auth, self.endpoint, dynamic_bucket, region=self.region
                )
                return self._buckets[actual_bucket_name]

        # If all attempts failed
        raise ValueError(
            f"Failed to get or create bucket for logical bucket {logical_bucket}"
        )

    def save(self, bucket: str, file_id: str, file_data: BinaryIO) -> str:
        """Save the file data to Aliyun OSS.

        Args:
            bucket (str): The logical bucket name
            file_id (str): The file ID
            file_data (BinaryIO): The file data

        Returns:
            str: The storage path (OSS URI)
        """
        # Get the actual OSS bucket
        oss_bucket = self._get_bucket(bucket)

        # Generate OSS object name based on whether we're using fixed bucket
        object_name = file_id
        if self.fixed_bucket:
            # When using a fixed bucket, we need to prefix with logical bucket name to
            # avoid conflicts
            object_name = f"{bucket}/{file_id}"

        # For large files, use multipart upload
        file_size = self._get_file_size(file_data)

        if file_size > 10 * self.save_chunk_size:  # If file is larger than 10MB
            logger.info(
                f"Using multipart upload for large file: {object_name} "
                f"(size: {file_size})"
            )
            self._multipart_upload(oss_bucket, object_name, file_data)
        else:
            logger.info(f"Uploading file using simple upload: {object_name}")
            try:
                oss_bucket.put_object(object_name, file_data)
            except oss2.exceptions.OssError as e:
                logger.error(
                    f"Failed to upload file {object_name} to bucket "
                    f"{oss_bucket.bucket_name}: {e}"
                )
                raise

        # Store the OSS bucket name and object path for future reference
        actual_bucket_name = oss_bucket.bucket_name

        # Format: oss://{actual_bucket_name}/{object_name}
        # We store both the actual bucket name and the object path in the URI
        # But we'll also keep the logical bucket in the external URI format
        return f"oss://{bucket}/{file_id}?actual_bucket={actual_bucket_name}&object_name={object_name}"  # noqa

    def _get_file_size(self, file_data: BinaryIO) -> int:
        """Get file size without consuming the file object.

        Args:
            file_data (BinaryIO): The file data

        Returns:
            int: The file size in bytes
        """
        current_pos = file_data.tell()
        file_data.seek(0, io.SEEK_END)
        size = file_data.tell()
        file_data.seek(current_pos)  # Reset the file pointer
        return size

    def _multipart_upload(
        self, oss_bucket: oss2.Bucket, file_id: str, file_data: BinaryIO
    ) -> None:
        """Handle multipart upload for large files.

        Args:
            oss_bucket (oss2.Bucket): OSS bucket object
            file_id (str): The file ID
            file_data (BinaryIO): The file data
        """
        # Initialize multipart upload
        upload_id = oss_bucket.init_multipart_upload(file_id).upload_id

        # Upload parts
        part_number = 1
        parts = []

        while True:
            chunk = file_data.read(self.save_chunk_size)
            if not chunk:
                break

            # Upload part
            etag = oss_bucket.upload_part(file_id, upload_id, part_number, chunk).etag
            parts.append(oss2.models.PartInfo(part_number, etag))
            part_number += 1

        # Complete multipart upload
        oss_bucket.complete_multipart_upload(file_id, upload_id, parts)

    def _parse_storage_path(self, storage_path: str) -> Dict[str, str]:
        """Parse the OSS storage path to extract actual bucket and object name.

        Args:
            storage_path (str): The storage path URI

        Returns:
            Dict[str, str]: A dictionary with actual_bucket and object_name keys
        """
        if not storage_path.startswith("oss://"):
            raise ValueError(f"Invalid storage path for Aliyun OSS: {storage_path}")

        # Example URI:
        # oss://logical_bucket/file_id?actual_bucket=oss_bucket&object_name=logical_bucket/file_id # noqa

        # Try to parse the URL parameters
        from urllib.parse import parse_qs, urlparse

        parsed_url = urlparse(storage_path)
        params = parse_qs(parsed_url.query)

        # Extract the parameters
        actual_bucket = params.get("actual_bucket", [None])[0]
        object_name = params.get("object_name", [None])[0]

        # Extract the logical bucket and file_id from the path
        path_parts = parsed_url.path.strip("/").split("/", 1)
        logical_bucket = path_parts[0] if path_parts else None
        logical_file_id = path_parts[1] if len(path_parts) > 1 else None

        # If parameters aren't in the URL (backward compatibility or simplified URL),
        # derive them from the logical values
        if not actual_bucket:
            # Try to use the bucket mapper to get the actual bucket
            actual_bucket = (
                self._map_bucket_name(logical_bucket) if logical_bucket else None
            )

        if not object_name:
            # If using fixed bucket, the object name includes the logical bucket
            # as prefix
            if self.fixed_bucket:
                object_name = (
                    f"{logical_bucket}/{logical_file_id}"
                    if logical_bucket and logical_file_id
                    else None
                )
            else:
                object_name = logical_file_id

        return {
            "logical_bucket": logical_bucket,
            "logical_file_id": logical_file_id,
            "actual_bucket": actual_bucket,
            "object_name": object_name,
        }

    def load(self, fm: FileMetadata) -> BinaryIO:
        """Load the file data from Aliyun OSS.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            BinaryIO: The file data as a binary IO object
        """
        # Parse the storage path
        path_info = self._parse_storage_path(fm.storage_path)

        # Get actual bucket and object name
        actual_bucket_name = path_info["actual_bucket"]
        object_name = path_info["object_name"]
        logical_bucket = path_info["logical_bucket"]

        # If we couldn't determine the actual bucket from the URI, try with the
        # logical bucket
        if not actual_bucket_name and logical_bucket:
            actual_bucket_name = self._map_bucket_name(logical_bucket)

        # Use the file_id as object name if object_name is still None
        if not object_name:
            object_name = fm.file_id
            # If using fixed bucket, prefix with logical bucket
            if self.fixed_bucket and logical_bucket:
                object_name = f"{logical_bucket}/{fm.file_id}"

        # Get the bucket object
        try:
            oss_bucket = oss2.Bucket(
                self.auth, self.endpoint, actual_bucket_name, region=self.region
            )

            # Get object as stream
            object_stream = oss_bucket.get_object(object_name)

            # Convert to BytesIO for compatibility
            content = io.BytesIO(object_stream.read())
            content.seek(0)
            return content
        except oss2.exceptions.NoSuchKey as e:
            logger.error(
                f"File {object_name} not found in bucket {actual_bucket_name}: {e}"
            )
            raise FileNotFoundError(
                f"File {object_name} not found in bucket {actual_bucket_name}"
            )
        except oss2.exceptions.OssError as e:
            logger.error(
                f"Failed to download file {object_name} from bucket "
                f"{actual_bucket_name}: {e}"
            )
            raise

    def delete(self, fm: FileMetadata) -> bool:
        """Delete the file data from Aliyun OSS.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            bool: True if the file was deleted, False otherwise
        """
        # Parse the storage path
        path_info = self._parse_storage_path(fm.storage_path)

        # Get actual bucket and object name
        actual_bucket_name = path_info["actual_bucket"]
        object_name = path_info["object_name"]
        logical_bucket = path_info["logical_bucket"]

        # If we couldn't determine the actual bucket from the URI, try with the
        # logical bucket
        if not actual_bucket_name and logical_bucket:
            actual_bucket_name = self._map_bucket_name(logical_bucket)

        # Use the file_id as object name if object_name is still None
        if not object_name:
            object_name = fm.file_id
            # If using fixed bucket, prefix with logical bucket
            if self.fixed_bucket and logical_bucket:
                object_name = f"{logical_bucket}/{fm.file_id}"

        try:
            # Get the bucket object
            oss_bucket = oss2.Bucket(
                self.auth, self.endpoint, actual_bucket_name, region=self.region
            )

            # Check if the object exists
            if not oss_bucket.object_exists(object_name):
                logger.warning(
                    f"File {object_name} does not exist in bucket {actual_bucket_name}"
                )
                return False

            # Delete the object
            oss_bucket.delete_object(object_name)
            logger.info(f"File {object_name} deleted from bucket {actual_bucket_name}")
            return True
        except oss2.exceptions.OssError as e:
            logger.error(
                f"Failed to delete file {object_name} from bucket {actual_bucket_name}:"
                f" {e}"
            )
            return False
