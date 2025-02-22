"""Hive Connector."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type, cast
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
    label=_("Apache Hive datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("A distributed fault-tolerant data warehouse system."),
)
@dataclass
class HiveParameters(BaseDatasourceParameters):
    """Hive connection parameters."""

    __type__ = "hive"

    # Basic connection parameters
    host: str = field(metadata={"help": _("Hive server host")})
    port: int = field(
        default=10000, metadata={"help": _("Hive server port, default 10000")}
    )
    database: str = field(
        default="default", metadata={"help": _("Database name, default 'default'")}
    )

    # Authentication parameters
    auth: str = field(
        default="NONE",
        metadata={
            "help": _("Authentication mode: NONE, NOSASL, LDAP, KERBEROS, CUSTOM"),
            "valid_values": ["NONE", "NOSASL", "LDAP", "KERBEROS", "CUSTOM"],
        },
    )
    username: str = field(
        default="", metadata={"help": _("Username for authentication")}
    )
    password: str = field(
        default="",
        metadata={
            "help": _("Password for LDAP or CUSTOM auth"),
            "tags": "privacy",
        },
    )

    # Kerberos parameters
    kerberos_service_name: str = field(
        default="hive", metadata={"help": _("Kerberos service name")}
    )

    # Transport parameters
    transport_mode: str = field(
        default="binary", metadata={"help": _("Transport mode: binary or http")}
    )
    # http_path: str = field(
    #     default="", metadata={"help": _("HTTP path for HTTP transport mode")}
    # )
    driver: str = field(
        default="hive",
        metadata={
            "help": _("Driver name for Hive, default is hive."),
        },
    )

    def engine_args(self) -> Optional[Dict[str, Any]]:
        """Get engine args."""
        connect_args = {"auth": self.auth}
        # username and password are not required for NONE and NOSASL
        if self.username:
            connect_args["username"] = self.username
        if self.password and self.auth in ("LDAP", "CUSTOM"):
            connect_args["password"] = self.password
        if self.auth == "KERBEROS":
            connect_args["kerberos_service_name"] = self.kerberos_service_name
        return {
            "connect_args": {k: v for k, v in connect_args.items() if v},
        }

    def create_connector(self) -> "HiveConnector":
        """Create Hive connector."""
        return HiveConnector.from_parameters(self)

    def db_url(self, ssl: bool = False, charset: Optional[str] = None):
        """Return database engine url."""
        if self.driver:
            scheme = self.driver
        elif self.transport_mode == "http":
            scheme = "hive+http"
        else:
            scheme = "hive"

        if self.username and self.password:
            auth_str = f"{quote(self.username)}:{urlquote(self.password)}@"
        else:
            auth_str = ""
        return f"{scheme}://{auth_str}{self.host}:{str(self.port)}/{self.database}"


class HiveConnector(RDBMSConnector):
    """Hive connector."""

    db_type: str = "hive"
    """db driver"""
    driver: str = "hive"
    """db dialect"""
    dialect: str = "hive"

    @classmethod
    def param_class(cls) -> Type[HiveParameters]:
        """Return the parameter class."""
        return HiveParameters

    @classmethod
    def from_parameters(cls, parameters: HiveParameters) -> "HiveConnector":
        """Create connector from parameters.

        More details:
        https://github.com/apache/kyuubi/blob/master/python/pyhive/hive.py
        """
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
    ) -> "HiveConnector":
        """Create a new HiveConnector from host, port, user, pwd, db_name."""
        db_url: str = f"{cls.driver}://{host}:{str(port)}/{db_name}"
        if user and pwd:
            db_url = (
                f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/"
                f"{db_name}"
            )
        return cast(HiveConnector, cls.from_uri(db_url, engine_args, **kwargs))

    def table_simple_info(self):
        """Get table simple info."""
        return []

    def get_users(self):
        """Get users."""
        return []

    def get_grants(self):
        """Get grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        """Get character_set of current database."""
        return "UTF-8"

    def _format_sql(self, sql: str) -> str:
        """Format sql."""
        sql = super()._format_sql(sql)
        # remove ';' at the end of sql
        return sql.rstrip(";")
