"""Summary classes for database, table, field and index."""

from typing import Dict, Iterable, List, Optional, Tuple


class DBSummary:
    """Database summary class."""

    def __init__(self, name: str):
        """Create a new DBSummary."""
        self.name = name
        self.summary: Optional[str] = None
        self.tables: Iterable[str] = []
        self.metadata: Optional[str] = None

    def get_summary(self) -> Optional[str]:
        """Get the summary."""
        return self.summary


class TableSummary:
    """Table summary class."""

    def __init__(self, name: str):
        """Create a new TableSummary."""
        self.name = name
        self.summary: Optional[str] = None
        self.fields: List[Tuple] = []
        self.indexes: List[Dict] = []


class FieldSummary:
    """Field summary class."""

    def __init__(self, name: str):
        """Create a new FieldSummary."""
        self.name = name
        self.summary = None
        self.data_type = None


class IndexSummary:
    """Index summary class."""

    def __init__(self, name: str):
        """Create a new IndexSummary."""
        self.name = name
        self.summary: Optional[str] = None
        self.bind_fields: List[str] = []
