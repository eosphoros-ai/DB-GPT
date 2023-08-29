import os


def has_path(filename):
    directory = os.path.dirname(filename)
    return bool(directory)
