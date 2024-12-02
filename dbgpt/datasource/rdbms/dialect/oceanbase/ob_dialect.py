"""OB Dialect support."""

import re

from sqlalchemy import util
from sqlalchemy.dialects import registry
from sqlalchemy.dialects.mysql import pymysql
from sqlalchemy.dialects.mysql.reflection import MySQLTableDefinitionParser, _re_compile


class OceanBaseTableDefinitionParser(MySQLTableDefinitionParser):
    """OceanBase table definition parser."""

    def __init__(self, dialect, preparer, *, default_schema=None):
        """Initialize OceanBaseTableDefinitionParser."""
        MySQLTableDefinitionParser.__init__(self, dialect, preparer)
        self.default_schema = default_schema

    def _prep_regexes(self):
        super()._prep_regexes()

        _final = self.preparer.final_quote
        quotes = dict(
            zip(
                ("iq", "fq", "esc_fq"),
                [
                    re.escape(s)
                    for s in (
                        self.preparer.initial_quote,
                        _final,
                        self.preparer._escape_identifier(_final),
                    )
                ],
            )
        )

        self._re_key = _re_compile(
            r"  "
            r"(?:(SPATIAL|VECTOR|(?P<type>\S+)) )?KEY"
            # r"(?:(?P<type>\S+) )?KEY"
            r"(?: +{iq}(?P<name>(?:{esc_fq}|[^{fq}])+){fq})?"
            r"(?: +USING +(?P<using_pre>\S+))?"
            r" +\((?P<columns>.+?)\)"
            r"(?: +USING +(?P<using_post>\S+))?"
            r"(?: +(KEY_)?BLOCK_SIZE *[ =]? *(?P<keyblock>\S+) *(LOCAL)?)?"
            r"(?: +WITH PARSER +(?P<parser>\S+))?"
            r"(?: +COMMENT +(?P<comment>(\x27\x27|\x27([^\x27])*?\x27)+))?"
            r"(?: +/\*(?P<version_sql>.+)\*/ *)?"
            r",?$".format(iq=quotes["iq"], esc_fq=quotes["esc_fq"], fq=quotes["fq"])
        )

        kw = quotes.copy()
        kw["on"] = "RESTRICT|CASCADE|SET NULL|NO ACTION"
        self._re_fk_constraint = _re_compile(
            r"  "
            r"CONSTRAINT +"
            r"{iq}(?P<name>(?:{esc_fq}|[^{fq}])+){fq} +"
            r"FOREIGN KEY +"
            r"\((?P<local>[^\)]+?)\) REFERENCES +"
            r"(?P<table>{iq}[^{fq}]+{fq}"
            r"(?:\.{iq}[^{fq}]+{fq})?) *"
            r"\((?P<foreign>(?:{iq}[^{fq}]+{fq}(?: *, *)?)+)\)"
            r"(?: +(?P<match>MATCH \w+))?"
            r"(?: +ON UPDATE (?P<onupdate>{on}))?"
            r"(?: +ON DELETE (?P<ondelete>{on}))?".format(
                iq=quotes["iq"], esc_fq=quotes["esc_fq"], fq=quotes["fq"], on=kw["on"]
            )
        )

    def _parse_constraints(self, line):
        """Parse a CONSTRAINT line."""
        ret = super()._parse_constraints(line)
        if ret:
            tp, spec = ret
            if tp == "partition":
                # do not handle partition
                return ret
            # logger.info(f"{tp} {spec}")
            if (
                tp == "fk_constraint"
                and len(spec["table"]) == 2
                and spec["table"][0] == self.default_schema
            ):
                spec["table"] = spec["table"][1:]
            if spec.get("onupdate", "").lower() == "restrict":
                spec["onupdate"] = None
            if spec.get("ondelete", "").lower() == "restrict":
                spec["ondelete"] = None
        return ret


class OBDialect(pymysql.MySQLDialect_pymysql):
    """OBDialect expend."""

    supports_statement_cache = True

    def __init__(self, **kwargs):
        """Initialize OBDialect."""
        try:
            from pyobvector import VECTOR  # type: ignore
        except ImportError:
            raise ImportError(
                "Could not import pyobvector package. "
                "Please install it with `pip install pyobvector`."
            )
        super().__init__(**kwargs)
        self.ischema_names["VECTOR"] = VECTOR

    def initialize(self, connection):
        """Ob dialect initialize."""
        super(OBDialect, self).initialize(connection)
        self._server_version_info = (5, 7, 19)
        self.server_version_info = (5, 7, 19)

    def _server_version_info(self, connection):
        """Ob set fixed version ending compatibility issue."""
        return (5, 7, 19)

    def get_isolation_level(self, dbapi_connection):
        """Ob set fixed version ending compatibility issue."""
        self.server_version_info = (5, 7, 19)
        return super(OBDialect, self).get_isolation_level(dbapi_connection)

    @util.memoized_property
    def _tabledef_parser(self):
        """Return the MySQLTableDefinitionParser, generate if needed.

        The deferred creation ensures that the dialect has
        retrieved server version information first.
        """
        preparer = self.identifier_preparer
        default_schema = self.default_schema_name
        return OceanBaseTableDefinitionParser(
            self, preparer, default_schema=default_schema
        )


registry.register("mysql.ob", __name__, "OBDialect")
