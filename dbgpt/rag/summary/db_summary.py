"""Summary classes for database, table, field and index."""


class DBSummary:
    """Database summary class."""

    def __init__(self, name: str):
        """Create a new DBSummary."""
        self.name = name
        self.summary = None
        self.tables = []
        self.metadata = str

    def get_summary(self):
        """Get the summary."""
        return self.summary


class TableSummary:
    """Table summary class."""

    def __init__(self, name: str):
        """Create a new TableSummary."""
        self.name = name
        self.summary = None
        self.fields = []
        self.indexes = []


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
        self.summary = None
        self.bind_fields = []
