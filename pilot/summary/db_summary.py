class DBSummary:
    def __init__(self, name):
        self.name = name
        self.summery = None
        self.tables = []
        self.metadata = str

    def get_summery(self):
        return self.summery


class TableSummary:
    def __init__(self, name):
        self.name = name
        self.summery = None
        self.fields = []
        self.indexes = []


class FieldSummary:
    def __init__(self, name):
        self.name = name
        self.summery = None
        self.data_type = None


class IndexSummary:
    def __init__(self, name):
        self.name = name
        self.summery = None
        self.bind_fields = []
