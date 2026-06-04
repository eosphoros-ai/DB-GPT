"""User-level configuration management for DB-GPT CLI.

Manages ``~/.dbgpt/configs/<profile>.toml`` — one flat TOML file per
profile — and a small ``~/.dbgpt/config.toml`` that records which profile
is active by default.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DBGPT_HOME = Path(os.environ.get("DBGPT_HOME", str(Path.home() / ".dbgpt")))
_CONFIGS_DIR = _DBGPT_HOME / "configs"
_ACTIVE_CONFIG = _DBGPT_HOME / "config.toml"

# Profile TOML files embed literal API keys (api_key, embedding_api_key) and so
# need to be readable only by the owning user. The DB-GPT home directory is
# restricted to 0o700 and the per-profile TOML files to 0o600. Wrapped in
# try/except because Windows does not support POSIX modes.
_SECRET_FILE_MODE = 0o600
_SECRET_DIR_MODE = 0o700


def _write_secret(path: Path, content: str) -> None:
    """Write ``content`` to ``path``, restricting both the file and its parent
    directory to owner-only on POSIX.

    Uses ``os.open(... O_CREAT, 0o600)`` so the file is atomically created with
    restricted permissions instead of being briefly world-readable between
    ``open("w")`` and a subsequent ``chmod`` (TOCTOU). Also tightens both the
    file and parent directory after the write to handle the case where they
    pre-existed at looser permissions (which cannot be fixed by O_CREAT alone).
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=_SECRET_DIR_MODE)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _SECRET_FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        path.chmod(_SECRET_FILE_MODE)
        path.parent.chmod(_SECRET_DIR_MODE)
    except (OSError, NotImplementedError):
        # Windows does not support POSIX modes. Best-effort.
        pass


def dbgpt_home() -> Path:
    """Return ``~/.dbgpt``, creating it if necessary."""
    _DBGPT_HOME.mkdir(parents=True, exist_ok=True, mode=_SECRET_DIR_MODE)
    return _DBGPT_HOME


def configs_dir() -> Path:
    """Return ``~/.dbgpt/configs/``, creating it if necessary."""
    _CONFIGS_DIR.mkdir(parents=True, exist_ok=True, mode=_SECRET_DIR_MODE)
    return _CONFIGS_DIR


def profile_config_path(profile_name: str) -> Path:
    """Return the path for a profile TOML, e.g. ``~/.dbgpt/configs/openai.toml``."""
    return configs_dir() / f"{profile_name}.toml"


def active_config_path() -> Path:
    """Return ``~/.dbgpt/config.toml``."""
    return _ACTIVE_CONFIG


# ---------------------------------------------------------------------------
# Active-profile record
# ---------------------------------------------------------------------------


def read_active_profile() -> Optional[str]:
    """Return the name of the active profile from ``~/.dbgpt/config.toml``.

    Returns:
        Optional[str]: Profile name, or *None* if not yet configured.
    """
    path = active_config_path()
    if not path.exists():
        return None
    try:
        import tomlkit  # type: ignore[import]

        data = tomlkit.loads(path.read_text(encoding="utf-8"))
        return data.get("default", {}).get("profile") or None
    except Exception:
        return None


def write_active_profile(profile_name: str) -> None:
    """Persist the active profile name to ``~/.dbgpt/config.toml``.

    Args:
        profile_name (str): The profile to activate.
    """
    import tomlkit  # type: ignore[import]

    path = active_config_path()
    dbgpt_home()  # ensure directory exists

    if path.exists():
        try:
            data = tomlkit.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = tomlkit.document()
    else:
        data = tomlkit.document()

    if "default" not in data:
        data["default"] = tomlkit.table()
    data["default"]["profile"] = profile_name  # type: ignore[index]
    path.write_text(tomlkit.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Profile TOML generation
# ---------------------------------------------------------------------------


def _escape_toml_string(value: str) -> str:
    """Escape backslashes and double quotes for TOML basic strings."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _render_profile_toml(
    spec: "ProfileSpec",  # noqa: F821
    api_key: Optional[str],
    llm_model: Optional[str] = None,
    embedding_model: Optional[str] = None,
    api_base: Optional[str] = None,
    embedding_api_key: Optional[str] = None,
) -> str:
    """Render a complete TOML config for the given profile.

    The generated file uses a literal API key when *api_key* is provided;
    otherwise it uses the ``${env:VAR}`` interpolation syntax so the server
    reads the key from the environment at runtime.

    Args:
        spec: A :class:`~dbgpt.cli._profiles.ProfileSpec` instance.
        api_key (Optional[str]): Literal API key value, or *None*.
        llm_model (Optional[str]): Override for the LLM model name. If *None*,
            uses ``spec.llm_model``.
        embedding_model (Optional[str]): Override for the embedding model name.
            If *None*, uses ``spec.embedding_model``.
        api_base (Optional[str]): Override for the LLM API base URL. If *None*,
            uses ``spec.llm_api_base``.
        embedding_api_key (Optional[str]): Literal embedding API key, or
            *None*.  When *None* and ``spec.embedding_env_var`` is set (and
            differs from ``spec.env_var``), the generated TOML will reference
            that separate env var instead of the LLM key.

    Returns:
        str: TOML content as a string.
    """
    from dbgpt.cli._profiles import ProfileSpec  # noqa: F401 (type-only)

    if api_key:
        api_key_value = _escape_toml_string(api_key)
    elif spec.env_var:
        api_key_value = f"${{env:{spec.env_var}:-sk-xxx}}"
    else:
        api_key_value = ""

    emb_env_var = spec.embedding_env_var or spec.env_var
    if embedding_api_key:
        emb_key_value = _escape_toml_string(embedding_api_key)
    elif api_key and not spec.embedding_env_var:
        emb_key_value = _escape_toml_string(api_key)
    elif emb_env_var:
        emb_key_value = f"${{env:{emb_env_var}:-sk-xxx}}"
    else:
        emb_key_value = ""

    if api_base:
        embedding_api_url = f"{api_base.rstrip('/')}/embeddings"
    else:
        embedding_api_url = spec.embedding_api_url

    data_dir = "pilot/meta_data/dbgpt.db"
    vector_dir = "pilot/data"

    lines = [
        f"# DB-GPT configuration — profile: {spec.name}",
        "# Generated by `dbgpt setup`",
        "",
        "[system]",
        "# Load language from environment variable(It is set by the hook)",
        'language = "${env:DBGPT_LANG:-en}"',
        "api_keys = []",
        'encrypt_key = "your_secret_key"',
        "",
        "# Server Configurations",
        "[service.web]",
        'host = "0.0.0.0"',
        "port = 5670",
        "",
        "[service.web.database]",
        'type = "sqlite"',
        f'path = "{data_dir}"',
        "",
        "[rag.storage]",
        "[rag.storage.vector]",
        'type = "chroma"',
        f'persist_path = "{vector_dir}"',
        "",
        "# Model Configurations",
        "[models]",
        "[[models.llms]]",
    ]

    use_env = getattr(spec, "use_env_interpolation", False) and not api_key

    if use_env:
        lines.append(f'name = "${{env:LLM_MODEL_NAME:-{spec.llm_model}}}"')
        lines.append(f'provider = "${{env:LLM_MODEL_PROVIDER:-{spec.llm_provider}}}"')
        effective_api_base = api_base or spec.llm_api_base
        if effective_api_base:
            lines.append(f'api_base = "${{env:OPENAI_API_BASE:-{effective_api_base}}}"')
        lines.append(f'api_key = "{api_key_value}"')
        lines.append("")
        lines.append("[[models.embeddings]]")
        lines.append(f'name = "${{env:EMBEDDING_MODEL_NAME:-{spec.embedding_model}}}"')
        lines.append(
            f'provider = "${{env:EMBEDDING_MODEL_PROVIDER:-{spec.embedding_provider}}}"'
        )
        lines.append(
            f'api_url = "${{env:EMBEDDING_MODEL_API_URL:-{embedding_api_url}}}"'
        )
        lines.append(f'api_key = "{emb_key_value}"')
    else:
        lines.append(f'name = "{llm_model or spec.llm_model}"')
        lines.append(f'provider = "{spec.llm_provider}"')

        effective_api_base = api_base or spec.llm_api_base
        if effective_api_base:
            lines.append(f'api_base = "{effective_api_base}"')

        lines.append(f'api_key = "{api_key_value}"')
        lines.append("")
        lines.append("[[models.embeddings]]")
        lines.append(f'name = "{embedding_model or spec.embedding_model}"')
        lines.append(f'provider = "{spec.embedding_provider}"')
        lines.append(f'api_url = "{embedding_api_url}"')
        lines.append(f'api_key = "{emb_key_value}"')

    # Append any provider-specific extras
    for extra in spec.extra_toml_lines:
        lines.append(extra)

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public write API
# ---------------------------------------------------------------------------


def write_profile_config(
    profile_name: str,
    api_key: Optional[str] = None,
    activate: bool = True,
    llm_model: Optional[str] = None,
    embedding_model: Optional[str] = None,
    api_base: Optional[str] = None,
    embedding_api_key: Optional[str] = None,
) -> Path:
    """Write (or overwrite) the TOML config for *profile_name*.

    Args:
        profile_name (str): One of the supported profile names.
        api_key (Optional[str]): Literal API key.  If *None*, env-var
            interpolation is used instead.
        activate (bool): Also update ``~/.dbgpt/config.toml`` to make this
            profile the active default.
        llm_model (Optional[str]): Override LLM model name. Uses spec default
            if *None*.
        embedding_model (Optional[str]): Override embedding model name. Uses
            spec default if *None*.
        api_base (Optional[str]): Override LLM API base URL. Uses spec default
            if *None*.
        embedding_api_key (Optional[str]): Literal embedding API key. When
            *None* and the profile has a separate ``embedding_env_var``, the
            generated TOML will reference that env var.

    Returns:
        Path: Path to the written config file.
    """
    from dbgpt.cli._profiles import get_profile

    spec = get_profile(profile_name)
    content = _render_profile_toml(
        spec,
        api_key,
        llm_model=llm_model,
        embedding_model=embedding_model,
        api_base=api_base,
        embedding_api_key=embedding_api_key,
    )
    path = profile_config_path(profile_name)
    # Profile TOML embeds literal api_key / embedding_api_key; route through
    # _write_secret so the file is atomically created at 0o600 (no TOCTOU
    # window where the API key is world-readable between create and chmod)
    # and the parent directory at 0o700.
    _write_secret(path, content)

    if activate:
        write_active_profile(profile_name)

    return path


def resolve_config_path(
    profile: Optional[str] = None,
    config: Optional[str] = None,
) -> Optional[str]:
    """Resolve which config file to use, in priority order.

    Priority:
    1. Explicit ``--config`` flag → use as-is.
    2. Explicit ``--profile`` flag → look up ``~/.dbgpt/configs/<profile>.toml``.
    3. Active profile from ``~/.dbgpt/config.toml``.
    4. Return *None* (caller should run the setup wizard).

    Args:
        profile (Optional[str]): Value of ``--profile`` CLI flag.
        config (Optional[str]): Value of ``--config`` CLI flag.

    Returns:
        Optional[str]: Absolute path to the config file, or *None*.
    """
    if config:
        return config

    if profile:
        path = profile_config_path(profile)
        if path.exists():
            return str(path)
        return None  # profile specified but not yet configured

    # Fall back to whatever is active
    active = read_active_profile()
    if active:
        path = profile_config_path(active)
        if path.exists():
            return str(path)

    return None
