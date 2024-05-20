"""Vertica dialect."""

from __future__ import absolute_import, division, print_function

from .base import VerticaDialect as BaseVerticaDialect


# noinspection PyAbstractClass, PyClassHasNoInit
class VerticaDialect(BaseVerticaDialect):
    """Vertica dialect class."""

    driver = "vertica_python"
    # TODO: support SQL caching, for more info see:
    # https://docs.sqlalchemy.org/en/14/core/connections.html#caching-for-third-party-dialects
    supports_statement_cache = False
    # No lastrowid support. TODO support SELECT LAST_INSERT_ID();
    postfetch_lastrowid = False

    @classmethod
    def dbapi(cls):
        """Get Driver."""
        vertica_python = __import__("vertica_python")
        return vertica_python
