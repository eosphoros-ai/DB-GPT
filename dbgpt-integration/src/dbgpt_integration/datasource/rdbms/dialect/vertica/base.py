"""Base class for Vertica dialect."""

from __future__ import (
    absolute_import,
    annotations,
    division,
    print_function,
    unicode_literals,
)

import logging
import re
from typing import Any, Optional

from sqlalchemy import sql
from sqlalchemy.engine import default, reflection

logger: logging.Logger = logging.getLogger(__name__)


class VerticaInspector(reflection.Inspector):
    """Reflection inspector for Vertica."""

    dialect: VerticaDialect

    def get_all_columns(self, table, schema: Optional[str] = None, **kw: Any):
        r"""Return all table columns names within a particular schema."""
        return self.dialect.get_all_columns(
            self.bind, table, schema, info_cache=self.info_cache, **kw
        )

    def get_table_comment(self, table_name: str, schema: Optional[str] = None, **kw):
        """Return comment of a table in a schema."""
        return self.dialect.get_table_comment(
            self.bind, table_name, schema, info_cache=self.info_cache, **kw
        )

    def get_view_columns(
        self, view: Optional[str] = None, schema: Optional[str] = None, **kw: Any
    ):
        r"""Return all view columns names within a particular schema."""
        return self.dialect.get_view_columns(
            self.bind, view, schema, info_cache=self.info_cache, **kw
        )

    def get_view_comment(
        self, view: Optional[str] = None, schema: Optional[str] = None, **kw
    ):
        r"""Return view comments within a particular schema."""
        return self.dialect.get_view_comment(
            self.bind, view, schema, info_cache=self.info_cache, **kw
        )


class VerticaDialect(default.DefaultDialect):
    """Vertica dialect."""

    name = "vertica"
    inspector = VerticaInspector

    def __init__(self, json_serializer=None, json_deserializer=None, **kwargs):
        """Init object."""
        default.DefaultDialect.__init__(self, **kwargs)

        self._json_deserializer = json_deserializer
        self._json_serializer = json_serializer

    def initialize(self, connection):
        """Init dialect."""
        super().initialize(connection)

    def _get_default_schema_name(self, connection):
        return connection.scalar(sql.text("SELECT current_schema()"))

    def _get_server_version_info(self, connection):
        v = connection.scalar(sql.text("SELECT version()"))
        m = re.match(r".*Vertica Analytic Database v(\d+)\.(\d+)\.(\d)+.*", v)
        if not m:
            raise AssertionError(
                "Could not determine version from string '%(ver)s'" % {"ver": v}
            )
        return tuple([int(x) for x in m.group(1, 2, 3) if x is not None])

    def create_connect_args(self, url):
        """Create args of connection."""
        opts = url.translate_connect_args(username="user")
        opts.update(url.query)
        return [], opts

    def has_table(self, connection, table_name, schema=None):
        """Check availability of a table."""
        return False

    def has_sequence(self, connection, sequence_name, schema=None):
        """Check availability of a sequence."""
        return False

    def has_type(self, connection, type_name):
        """Check availability of a type."""
        return False

    def get_schema_names(self, connection, **kw):
        """Return names of all schemas."""
        return []

    def get_table_comment(self, connection, table_name, schema=None, **kw):
        """Return comment of a table in a schema."""
        return {"text": table_name}

    def get_table_names(self, connection, schema=None, **kw):
        """Get names of tables in a schema."""
        return []

    def get_temp_table_names(self, connection, schema=None, **kw):
        """Get names of temp tables in a schema."""
        return []

    def get_view_names(self, connection, schema=None, **kw):
        """Get names of views in a schema."""
        return []

    def get_view_definition(self, connection, view_name, schema=None, **kw):
        """Get definition of views in a schema."""
        return view_name

    def get_temp_view_names(self, connection, schema=None, **kw):
        """Get names of temp views in a schema."""
        return []

    def get_unique_constraints(self, connection, table_name, schema=None, **kw):
        """Get unique constrains of a table in a schema."""
        return []

    def get_check_constraints(self, connection, table_name, schema=None, **kw):
        """Get checks of a table in a schema."""
        return []

    def normalize_name(self, name):
        """Normalize name."""
        name = name and name.rstrip()
        if name is None:
            return None
        return name.lower()

    def denormalize_name(self, name):
        """Denormalize name."""
        return name

    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        """Get poreignn keys of a table in a schema."""
        return []

    def get_indexes(self, connection, table_name, schema, **kw):
        """Get indexes of a table in a schema."""
        return []

    def visit_create_index(self, create):
        """Disable index creation since that's not a thing in Vertica."""
        return None

    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        """Get primary keye of a table in a schema."""
        return None

    def get_all_columns(self, connection, table, schema=None, **kw):
        """Get all columns of a table in a schema."""
        return []

    def get_columns(self, connection, table_name, schema=None, **kw):
        """Get all columns of a table in a schema."""
        return self.get_all_columns(connection, table_name, schema)

    def get_view_columns(self, connection, view, schema=None, **kw):
        """Get columns of views in a schema."""
        return []

    def get_view_comment(self, connection, view, schema=None, **kw):
        """Get comment of view."""
        return {"text": view}
