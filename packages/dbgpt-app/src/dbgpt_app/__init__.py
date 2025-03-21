"""The app package.

This package will not be uploaded to PyPI. So, your can't import it if some other
package depends on it.
"""

from ._version import version as __version__  # noqa: F401

__ALL__ = ["__version__"]
