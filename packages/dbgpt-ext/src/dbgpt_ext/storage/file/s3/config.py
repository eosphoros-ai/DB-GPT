from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from dbgpt.core.interface.file import StorageBackend, StorageBackendConfig
from dbgpt.util.i18n_utils import _


@dataclass
class S3StorageConfig(StorageBackendConfig):
    __type__ = "s3"
    endpoint: str = field(
        metadata={
            "help": _(
                "The endpoint of the s3 server. e.g. https://s3.us-east-1.amazonaws.com"
            )
        },
    )
    region: str = field(
        metadata={"help": _("The region of the s3 server. e.g. us-east-1")},
    )
    access_key_id: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The access key ID of the s3 server. You can also set it in the "
                "environment variable AWS_ACCESS_KEY_ID"
            ),
            "tags": "privacy",
        },
    )
    access_key_secret: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The access key secret of the s3 server. You can also set it in the "
                "environment variable AWS_SECRET_ACCESS_KEY"
            ),
            "tags": "privacy",
        },
    )
    use_environment_credentials: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to use the environment variables AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY as the credentials. Default is False."
            ),
        },
    )
    fixed_bucket: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The fixed bucket name to use. If set, all logical buckets in DB-GPT "
                "will be mapped to this bucket. We suggest you set this value to avoid "
                "bucket name conflicts."
            )
        },
    )
    bucket_prefix: Optional[str] = field(
        default="dbgpt-fs-",
        metadata={
            "help": _(
                "The prefix of the bucket name. If set, all logical buckets in DB-GPT "
                "will be prefixed with this value. Just work when fixed_bucket is None."
            )
        },
    )
    auto_create_bucket: Optional[bool] = field(
        default=True,
        metadata={
            "help": _(
                "Whether to create the bucket automatically if it does not exist. "
                "If set to False, the bucket must exist before using it."
            )
        },
    )
    save_chunk_size: Optional[int] = field(
        default=1024 * 1024,
        metadata={
            "help": _(
                "The chunk size when saving the file. When the file is larger 10x than "
                "this value, it will be uploaded in multiple parts. Default is 1M."
            )
        },
    )
    signature_version: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The signature version of the s3 server. "
                "e.g. s3v4, s3v2, None (default)"
            )
        },
    )
    s3_config: Optional[Dict[str, Any]] = field(
        default_factory=dict,
        metadata={
            "help": _("The additional configuration for the S3 client."),
        },
    )

    def create_storage(self) -> StorageBackend:
        from .s3_storage import S3Storage

        return S3Storage(
            endpoint_url=self.endpoint,
            region_name=self.region,
            access_key_id=self.access_key_id,
            secret_access_key=self.access_key_secret,
            use_environment_credentials=self.use_environment_credentials,
            fixed_bucket=self.fixed_bucket,
            bucket_prefix=self.bucket_prefix,
            auto_create_bucket=self.auto_create_bucket,
            save_chunk_size=self.save_chunk_size,
            signature_version=self.signature_version,
            s3_config=self.s3_config,
        )
