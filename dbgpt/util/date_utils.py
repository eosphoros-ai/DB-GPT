import datetime


def is_datetime(value):
    return isinstance(value, datetime.datetime)


def convert_datetime_in_row(row):
    return [
        value.strftime("%Y-%m-%d %H:%M:%S") if is_datetime(value) else value
        for value in row
    ]
