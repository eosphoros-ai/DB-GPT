"""S3 compatible storage backend."""

import hashlib
import io
import logging
import os
import random
import time
from typing import BinaryIO, Callable, Dict, Optional, Union
from urllib.parse import parse_qs, urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from dbgpt.core.interface.file import FileMetadata, StorageBackend

logger = logging.getLogger(__name__)


class S3Storage(StorageBackend):
    """S3 compatible storage backend implementation."""

    storage_type: str = "s3"

    def __init__(
        self,
        endpoint_url: str,
        region_name: str,
        access_key_id: str,
        secret_access_key: str,
        save_chunk_size: int = 1024 * 1024,
        use_environment_credentials: bool = False,
        fixed_bucket: Optional[str] = None,
        bucket_prefix: str = "dbgpt-fs-",
        bucket_mapper: Optional[Callable[[str], str]] = None,
        auto_create_bucket: bool = True,
        signature_version: Optional[str] = None,
        s3_config: Optional[Dict[str, Union[str, int]]] = None,
    ):
        """Initialize the S3 compatible storage backend.

        Args:
            endpoint_url (str): S3 endpoint URL, e.g.,
                "https://s3.us-east-1.amazonaws.com"
            region_name (str): S3 region, e.g., "us-east-1"
            access_key_id (str): AWS/S3 Access Key ID
            secret_access_key (str): AWS/S3 Secret Access Key
            save_chunk_size (int, optional): Chunk size for saving files. Defaults to
                1024*1024 (1MB).
            use_environment_credentials (bool, optional): Whether to use credentials
                from environment variables. Defaults to False.
            fixed_bucket (Optional[str], optional): A fixed S3 bucket to use for all
                operations. If provided, all logical buckets will be mapped to this
                single bucket. Defaults to None.
            bucket_prefix (str, optional): Prefix for dynamically created buckets.
                Defaults to "dbgpt-fs-".
            bucket_mapper (Optional[Callable[[str], str]], optional): Custom function
                to map logical bucket names to actual S3 bucket names. Defaults to None.
            auto_create_bucket (bool, optional): Whether to automatically create
                buckets that don't exist. Defaults to True.
            signature_version (str, optional): S3 signature version to use.
            s3_config (Optional[Dict[str, Union[str, int]]], optional): Additional
                S3 configuration options. Defaults to None.
        """
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self._save_chunk_size = save_chunk_size
        self.fixed_bucket = fixed_bucket
        self.bucket_prefix = bucket_prefix
        self.custom_bucket_mapper = bucket_mapper
        self.auto_create_bucket = auto_create_bucket
        self.signature_version = signature_version

        # Build S3 client configuration
        if not s3_config:
            s3_config = {
                "s3": {
                    # Use virtual addressing style
                    "addressing_style": "virtual",
                },
                "signature_version": signature_version or "v4",
            }
        if "request_checksum_calculation" not in s3_config:
            s3_config["request_checksum_calculation"] = "when_required"
        if "response_checksum_validation" not in s3_config:
            s3_config["response_checksum_validation"] = "when_required"
        config = Config(**s3_config)

        # Initialize S3 authentication
        if use_environment_credentials:
            # Check required environment variables
            required_env_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
            for var in required_env_vars:
                if var not in os.environ:
                    raise ValueError(f"Environment variable {var} is not set.")

            # Use environment credentials
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region_name,
                config=config,
            )
        else:
            if not access_key_id or not secret_access_key:
                raise ValueError(
                    "Access key ID and secret are required when not using environment "
                    "credentials"
                )
            # Use provided credentials
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region_name,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=config,
            )

        # Create fixed bucket if specified
        if self.fixed_bucket and self.auto_create_bucket:
            self._ensure_bucket_exists(self.fixed_bucket)

    @property
    def save_chunk_size(self) -> int:
        """Get the save chunk size."""
        return self._save_chunk_size

    def _map_bucket_name(self, logical_bucket: str) -> str:
        """Map logical bucket name to actual S3 bucket name.

        Args:
            logical_bucket (str): Logical bucket name used by the application

        Returns:
            str: Actual S3 bucket name to use
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
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} exists")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_msg = str(e)

            logger.info(
                f"Bucket check failed with error_code={error_code}, msg={error_msg}"
            )

            # Bucket doesn't exist or we don't have permission to access it
            if error_code in ["404", "403", "NoSuchBucket", "Forbidden"]:
                if not self.auto_create_bucket:
                    logger.warning(
                        f"Bucket {bucket_name} does not exist and auto_create_bucket "
                        "is False"
                    )
                    return False

                # Create bucket
                try:
                    logger.info(f"Creating bucket {bucket_name}")

                    # Try different creation methods to adapt to different
                    # S3-compatible APIs
                    creation_methods = [
                        # Method 1: Use LocationConstraint
                        lambda: self.s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": self.region_name
                            },
                        ),
                        # Method 2: Without LocationConstraint
                        lambda: self.s3_client.create_bucket(Bucket=bucket_name),
                        # Method 3: Use empty CreateBucketConfiguration
                        lambda: self.s3_client.create_bucket(
                            Bucket=bucket_name, CreateBucketConfiguration={}
                        ),
                    ]

                    # Try different creation methods
                    last_error = None
                    for create_method in creation_methods:
                        try:
                            create_method()
                            logger.info(f"Successfully created bucket {bucket_name}")
                            return True
                        except ClientError as method_error:
                            logger.info(
                                f"Bucket creation method failed: {method_error}"
                            )
                            last_error = method_error
                            continue

                    # If all methods failed, raise the last error
                    if last_error:
                        raise last_error

                    return False

                except ClientError as create_error:
                    # Handle the case where bucket name is already taken by someone else
                    logger.error(
                        f"Failed to create bucket {bucket_name}: {create_error}"
                    )
                    if "BucketAlreadyExists" in str(create_error):
                        logger.warning(
                            f"Bucket name {bucket_name} already exists and is owned by "
                            "someone else"
                        )
                    return False
            else:
                # Some other error
                logger.error(f"Failed to check bucket {bucket_name}: {e}")
                return False

    def save(self, bucket: str, file_id: str, file_data: BinaryIO) -> str:
        """Save the file data to S3.

        Args:
            bucket (str): The logical bucket name
            file_id (str): The file ID
            file_data (BinaryIO): The file data

        Returns:
            str: The storage path (S3 URI)
        """
        # Get the actual S3 bucket
        actual_bucket_name = self._map_bucket_name(bucket)
        logger.info(
            f"Mapped logical bucket '{bucket}' to actual bucket '{actual_bucket_name}'"
        )

        # Ensure bucket exists
        bucket_exists = self._ensure_bucket_exists(actual_bucket_name)

        if not bucket_exists:
            logger.warning(
                f"Could not ensure bucket {actual_bucket_name} exists, trying "
                "alternatives"
            )

            # Try to create a dynamic bucket if we're not using a fixed bucket
            if not self.fixed_bucket and self.auto_create_bucket:
                dynamic_bucket = self._generate_dynamic_bucket_name()
                logger.info(
                    f"Attempting to create dynamic bucket {dynamic_bucket} for logical "
                    f"bucket {bucket}"
                )

                if self._ensure_bucket_exists(dynamic_bucket):
                    logger.info(f"Successfully created dynamic bucket {dynamic_bucket}")
                    actual_bucket_name = dynamic_bucket
                else:
                    error_msg = (
                        f"Failed to get or create bucket for logical bucket {bucket}"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            else:
                error_msg = (
                    f"Failed to get or create bucket for logical bucket {bucket}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        # Generate S3 object key based on whether we're using fixed bucket
        object_key = file_id
        if self.fixed_bucket:
            # When using a fixed bucket, we need to prefix with logical bucket name to
            # avoid conflicts
            object_key = f"{bucket}/{file_id}"

        # For large files, use multipart upload
        file_size = self._get_file_size(file_data)

        if file_size > 10 * self.save_chunk_size:  # If file is larger than 10MB
            logger.info(
                f"Using multipart upload for large file: {object_key} "
                f"(size: {file_size})"
            )
            self._multipart_upload(actual_bucket_name, object_key, file_data)
        else:
            logger.info(f"Uploading file using simple upload: {object_key}")
            try:
                # Reset the file pointer to the beginning
                file_data.seek(0)

                # Read the file content into memory
                file_content = file_data.read()

                # Use put_object for small files
                self.s3_client.put_object(
                    Bucket=actual_bucket_name, Key=object_key, Body=file_content
                )
            except ClientError as e:
                logger.error(
                    f"Failed to upload file {object_key} to bucket "
                    f"{actual_bucket_name}: {e}"
                )
                raise

        # Format: s3://{logical_bucket}/{file_id}?actual_bucket={actual_bucket_name}&object_key={object_key} # noqa
        return f"s3://{bucket}/{file_id}?actual_bucket={actual_bucket_name}&object_key={object_key}"  # noqa

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
        self, bucket_name: str, object_key: str, file_data: BinaryIO
    ) -> None:
        """Handle multipart upload for large files.

        Args:
            bucket_name (str): S3 bucket name
            object_key (str): The object key (file path in S3)
            file_data (BinaryIO): The file data
        """
        # Initialize multipart upload
        try:
            mpu = self.s3_client.create_multipart_upload(
                Bucket=bucket_name, Key=object_key
            )
            upload_id = mpu["UploadId"]

            # Upload parts
            part_number = 1
            parts = []
            file_data.seek(0)  # Make sure we're at the beginning of the file

            while True:
                # Read the chunk
                chunk = file_data.read(self.save_chunk_size)
                if not chunk:
                    break

                # Upload the part
                response = self.s3_client.upload_part(
                    Bucket=bucket_name,
                    Key=object_key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk,
                )

                parts.append({"PartNumber": part_number, "ETag": response["ETag"]})

                part_number += 1

            # Complete multipart upload
            self.s3_client.complete_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except ClientError as e:
            logger.error(f"Error in multipart upload: {e}")
            # Attempt to abort the multipart upload if it was initialized
            if "upload_id" in locals():
                try:
                    self.s3_client.abort_multipart_upload(
                        Bucket=bucket_name, Key=object_key, UploadId=upload_id
                    )
                except ClientError as abort_error:
                    logger.error(f"Error aborting multipart upload: {abort_error}")
            raise

    def _parse_storage_path(self, storage_path: str) -> Dict[str, str]:
        """Parse the S3 storage path to extract actual bucket and object key.

        Args:
            storage_path (str): The storage path URI

        Returns:
            Dict[str, str]: A dictionary with actual_bucket and object_key keys
        """
        if not storage_path.startswith("s3://"):
            raise ValueError(f"Invalid storage path for S3: {storage_path}")

        # Example URI:
        # s3://logical_bucket/file_id?actual_bucket=s3_bucket&object_key=logical_bucket/file_id # noqa

        # Parse the URL
        parsed_url = urlparse(storage_path)
        params = parse_qs(parsed_url.query)

        # Extract the parameters
        actual_bucket = params.get("actual_bucket", [None])[0]
        object_key = params.get("object_key", [None])[0]

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

        if not object_key:
            # If using fixed bucket, the object key includes the logical bucket
            # as prefix
            if self.fixed_bucket:
                object_key = (
                    f"{logical_bucket}/{logical_file_id}"
                    if logical_bucket and logical_file_id
                    else None
                )
            else:
                object_key = logical_file_id

        return {
            "logical_bucket": logical_bucket,
            "logical_file_id": logical_file_id,
            "actual_bucket": actual_bucket,
            "object_key": object_key,
        }

    def load(self, fm: FileMetadata) -> BinaryIO:
        """Load the file data from S3.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            BinaryIO: The file data as a binary IO object
        """
        # Parse the storage path
        path_info = self._parse_storage_path(fm.storage_path)

        # Get actual bucket and object key
        actual_bucket_name = path_info["actual_bucket"]
        object_key = path_info["object_key"]
        logical_bucket = path_info["logical_bucket"]

        # If we couldn't determine the actual bucket from the URI, try with the
        # logical bucket
        if not actual_bucket_name and logical_bucket:
            actual_bucket_name = self._map_bucket_name(logical_bucket)

        # Use the file_id as object key if object_key is still None
        if not object_key:
            object_key = fm.file_id
            # If using fixed bucket, prefix with logical bucket
            if self.fixed_bucket and logical_bucket:
                object_key = f"{logical_bucket}/{fm.file_id}"

        try:
            # Get object from S3
            response = self.s3_client.get_object(
                Bucket=actual_bucket_name, Key=object_key
            )

            # Read the streaming body into a BytesIO object
            content = io.BytesIO()
            body = response["Body"]

            # Stream the data in chunks
            while True:
                chunk = body.read(self.save_chunk_size)
                if not chunk:
                    break
                content.write(chunk)

            content.seek(0)
            return content
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                logger.error(
                    f"File {object_key} not found in bucket {actual_bucket_name}: {e}"
                )
                raise FileNotFoundError(
                    f"File {object_key} not found in bucket {actual_bucket_name}"
                )
            logger.error(
                f"Failed to download file {object_key} from bucket "
                f"{actual_bucket_name}: {e}"
            )
            raise

    def delete(self, fm: FileMetadata) -> bool:
        """Delete the file data from S3.

        Args:
            fm (FileMetadata): The file metadata

        Returns:
            bool: True if the file was deleted, False otherwise
        """
        # Parse the storage path
        path_info = self._parse_storage_path(fm.storage_path)

        # Get actual bucket and object key
        actual_bucket_name = path_info["actual_bucket"]
        object_key = path_info["object_key"]
        logical_bucket = path_info["logical_bucket"]

        # If we couldn't determine the actual bucket from the URI, try with the
        # logical bucket
        if not actual_bucket_name and logical_bucket:
            actual_bucket_name = self._map_bucket_name(logical_bucket)

        # Use the file_id as object key if object_key is still None
        if not object_key:
            object_key = fm.file_id
            # If using fixed bucket, prefix with logical bucket
            if self.fixed_bucket and logical_bucket:
                object_key = f"{logical_bucket}/{fm.file_id}"

        try:
            # Check if the object exists
            try:
                self.s3_client.head_object(Bucket=actual_bucket_name, Key=object_key)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code == "404" or error_code == "NoSuchKey":
                    logger.warning(
                        f"File {object_key} does not exist in bucket "
                        f"{actual_bucket_name}"
                    )
                    return False
                raise

            # Delete the object
            self.s3_client.delete_object(Bucket=actual_bucket_name, Key=object_key)

            logger.info(f"File {object_key} deleted from bucket {actual_bucket_name}")
            return True
        except ClientError as e:
            logger.error(
                f"Failed to delete file {object_key} from bucket {actual_bucket_name}:"
                f" {e}"
            )
            return False
