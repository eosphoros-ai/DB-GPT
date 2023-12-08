class DBSummary:
    def __init__(self, name):
        self.name = name
        self.summary = None
        self.tables = []
        self.metadata = str

    def get_summary(self):
        return self.summary


class TableSummary:
    def __init__(self, name):
        self.name = name
        self.summary = None
        self.fields = []
        self.indexes = []


class FieldSummary:
    def __init__(self, name):
        self.name = name
        self.summary = None
        self.data_type = None


class IndexSummary:
    def __init__(self, name):
        self.name = name
        self.summary = None
        self.bind_fields = []
