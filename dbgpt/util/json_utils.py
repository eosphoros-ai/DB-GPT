import json
from datetime import date, datetime


def serialize(obj):
    if isinstance(obj, date):
        return obj.isoformat()


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
