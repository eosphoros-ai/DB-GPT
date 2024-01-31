"""HTTP utilities."""


import re


def join_paths(*paths):
    """Join multiple paths into one path.

    Delete the spaces and slashes at both ends of each path, and ensure that there is
    only one slash between the paths.
    """
    stripped_paths = [
        re.sub(r"^[/\s]+|[/\s]+$", "", path) for path in paths if path.strip("/")
    ]
    full_path = "/".join(stripped_paths)
    # Replace multiple consecutive slashes with a single slash
    return re.sub(r"/{2,}", "/", "/" + full_path)
