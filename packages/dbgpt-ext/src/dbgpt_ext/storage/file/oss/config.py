from dataclasses import dataclass, field
from typing import Optional

from dbgpt.core.interface.file import StorageBackend, StorageBackendConfig
from dbgpt.util.i18n_utils import _


@dataclass
class OSSStorageConfig(StorageBackendConfig):
    __type__ = "oss"
    endpoint: str = field(
        metadata={
            "help": _(
                "The endpoint of the OSS server. "
                "e.g. https://oss-cn-hangzhou.aliyuncs.com"
            )
        },
    )
    region: str = field(
        metadata={"help": _("The region of the OSS server. e.g. cn-hangzhou")},
    )
    access_key_id: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The access key ID of the OSS server. You can also set it in the "
                "environment variable OSS_ACCESS_KEY_ID"
            ),
            "tags": "privacy",
        },
    )
    access_key_secret: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The access key secret of the OSS server. You can also set it in the "
                "environment variable OSS_ACCESS_KEY_SECRET"
            ),
            "tags": "privacy",
        },
    )
    use_environment_credentials: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to use the environment variables OSS_ACCESS_KEY_ID and "
                "OSS_ACCESS_KEY_SECRET as the credentials. Default is False."
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

    def create_storage(self) -> StorageBackend:
        from .oss_storage import AliyunOSSStorage

        return AliyunOSSStorage(
            endpoint=self.endpoint,
            region=self.region,
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
            use_environment_credentials=self.use_environment_credentials,
            fixed_bucket=self.fixed_bucket,
            bucket_prefix=self.bucket_prefix,
            auto_create_bucket=self.auto_create_bucket,
            save_chunk_size=self.save_chunk_size,
        )
