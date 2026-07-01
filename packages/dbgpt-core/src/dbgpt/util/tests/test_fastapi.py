"""Tests for ``dbgpt.util.fastapi`` helpers."""

from dbgpt.util.fastapi import build_cors_config

_DEFAULT_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def test_wildcard_disables_credentials():
    """``"*"`` must return all origins with credentials disabled (W3C)."""
    cfg = build_cors_config("*")
    assert cfg["allow_origins"] == ["*"]
    assert cfg["allow_credentials"] is False
    assert cfg["allow_methods"] == _DEFAULT_METHODS
    assert cfg["allow_headers"] == ["*"]


def test_empty_or_none_treated_as_wildcard():
    """Empty string or None should fall back to ``"*"`` (safe default)."""
    assert build_cors_config("")["allow_origins"] == ["*"]
    assert build_cors_config("")["allow_credentials"] is False
    assert build_cors_config(None)["allow_origins"] == ["*"]
    assert build_cors_config(None)["allow_credentials"] is False


def test_explicit_origins_enable_credentials_and_trim():
    """Explicit origin list enables credentials and trims whitespace/blanks."""
    cfg = build_cors_config("  http://localhost:3000 , https://your-app.com ,  ,")
    assert cfg["allow_origins"] == ["http://localhost:3000", "https://your-app.com"]
    assert cfg["allow_credentials"] is True


def test_mixed_wildcard_treated_as_wildcard():
    """Any wildcard entry disables credentials to keep CORS headers valid."""
    cfg = build_cors_config("*, https://your-app.com")
    assert cfg["allow_origins"] == ["*"]
    assert cfg["allow_credentials"] is False


def test_single_explicit_origin():
    """A single explicit origin still enables credentials."""
    cfg = build_cors_config("https://your-app.com")
    assert cfg["allow_origins"] == ["https://your-app.com"]
    assert cfg["allow_credentials"] is True
