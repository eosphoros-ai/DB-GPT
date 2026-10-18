"""Built-in knowledge source connectors (self-register via decorator)."""

from . import feishu_drive, feishu_wiki, rss, yuque  # noqa: F401

__all__ = ["rss", "feishu_wiki", "feishu_drive", "yuque"]
