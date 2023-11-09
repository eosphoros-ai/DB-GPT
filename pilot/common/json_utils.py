import json
from datetime import date

def serialize(obj):
    if isinstance(obj, date):
        return obj.isoformat()