"""MaxCompute (ODPS) Connector."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

from sqlalchemy import create_engine

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.util.i18n_utils import _


@auto_register_resource(
    label=_("Alibaba Cloud MaxCompute datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Alibaba Cloud MaxCompute (ODPS), a fully managed, large-scale data "
        "warehouse service for batch analytics."
    ),
)
@dataclass
class MaxComputeParameters(BaseDatasourceParameters):
    """MaxCompute connection parameters."""

    __type__ = "maxcompute"

    # A MaxCompute project acts as the database in DB-GPT's model.
    project: str = field(metadata={"help": _("MaxCompute project name")})
    access_id: str = field(
        default="",
        metadata={"help": _("Alibaba Cloud AccessKey ID")},
    )
    access_key: str = field(
        default="",
        metadata={
            "help": _("Alibaba Cloud AccessKey Secret"),
            "tags": "privacy",
        },
    )
    endpoint: str = field(
        default="https://service.cn-hangzhou.maxcompute.aliyun.com/api",
        metadata={
            "help": _(
                "MaxCompute service endpoint, e.g. "
                "https://service.cn-hangzhou.maxcompute.aliyun.com/api"
            )
        },
    )
    driver: str = field(
        default="odps",
        metadata={"help": _("SQLAlchemy driver name for MaxCompute, default 'odps'")},
    )

    @classmethod
    def _persisted_state_mapping(cls) -> Dict[str, str]:
        """Return the mapping of persisted state.

        MaxCompute's connection fields don't match the default
        host/port/user/password/database mapping, so we map them explicitly to the
        fixed ``connect_config`` columns. This keeps the semantics consistent with
        ``from_uri_db`` (endpoint->host, access_id->user, access_key->password,
        project->database), ensuring both datasource creation (``db_name`` is
        populated, satisfying the NOT NULL constraint) and connector rebuild work.
        """
        return {
            "endpoint": "db_host",
            "access_id": "db_user",
            "access_key": "db_pwd",
            "project": "db_name",
        }

    def engine_args(self) -> Optional[Dict[str, Any]]:
        """Get engine args."""
        return {}

    def create_connector(self) -> "MaxComputeConnector":
        """Create MaxCompute connector."""
        return MaxComputeConnector.from_parameters(self)

    def db_url(self, ssl: bool = False, charset: Optional[str] = None) -> str:
        """Return database engine url.

        The PyODPS SQLAlchemy dialect uses the form::

            odps://<access_id>:<access_key>@<project>/?endpoint=<endpoint>
        """
        if self.access_id and self.access_key:
            auth_str = f"{quote(self.access_id)}:{urlquote(self.access_key)}@"
        else:
            auth_str = ""
        url = f"{self.driver}://{auth_str}{quote(self.project)}/"
        if self.endpoint:
            url += f"?endpoint={urlquote(self.endpoint)}"
        return url


class MaxComputeConnector(RDBMSConnector):
    """MaxCompute (ODPS) connector.

    Connects to Alibaba Cloud MaxCompute through the PyODPS SQLAlchemy dialect.
    Requires the ``pyodps`` package (``pip install "dbgpt-ext[datasource_maxcompute]"``
    or ``pip install pyodps``).
    """

    db_type: str = "maxcompute"
    """db driver"""
    driver: str = "odps"
    """db dialect"""
    dialect: str = "odps"

    @classmethod
    def param_class(cls) -> Type[MaxComputeParameters]:
        """Return the parameter class."""
        return MaxComputeParameters

    @classmethod
    def from_parameters(cls, parameters: MaxComputeParameters) -> "MaxComputeConnector":
        """Create MaxCompute connector from parameters."""
        db_url = parameters.db_url()
        engine_args = parameters.engine_args() or {}
        return cls(create_engine(db_url, **engine_args))

    @classmethod
    def from_uri_db(
        cls,
        host: str,
        port: int,
        user: str,
        pwd: str,
        db_name: str,
        engine_args: Optional[dict] = None,
        **kwargs: Any,
    ) -> "MaxComputeConnector":
        """Create a new MaxComputeConnector from connection information.

        ``host`` is interpreted as the MaxCompute endpoint, ``user``/``pwd`` as the
        AccessKey id/secret, and ``db_name`` as the MaxCompute project. ``port`` is
        unused and kept only for interface compatibility.
        """
        if user and pwd:
            auth_str = f"{quote(user)}:{urlquote(pwd)}@"
        else:
            auth_str = ""
        db_url = f"{cls.driver}://{auth_str}{quote(db_name)}/"
        if host:
            db_url += f"?endpoint={urlquote(host)}"
        return cast(MaxComputeConnector, cls.from_uri(db_url, engine_args, **kwargs))

    def table_simple_info(self) -> List[Any]:
        """Get table simple info.

        MaxCompute does not expose an ``information_schema`` compatible view, so the
        generic implementation is skipped.
        """
        return []

    def get_users(self) -> List[Any]:
        """Get users."""
        return []

    def get_grants(self) -> List[Any]:
        """Get grants."""
        return []

    def get_collation(self) -> str:
        """Get collation."""
        return "UTF-8"

    def get_charset(self) -> str:
        """Get character_set of current database."""
        return "UTF-8"

    def _format_sql(self, sql: str) -> str:
        """Format sql."""
        sql = super()._format_sql(sql)
        # MaxCompute rejects a trailing ';' in single-statement submissions.
        return sql.rstrip(";")
