"""Configuration and subprocess bootstrap for the pi harness engine.

Covers:
- :class:`PiHarnessConfig`: everything needed to spawn one pi RPC child;
- :meth:`PiHarnessConfig.build_command`: the CLI argv (mode/cwd/tools/model);
- :meth:`PiHarnessConfig.prepare_agent_dir`: an isolated
  ``PI_CODING_AGENT_DIR`` with a ``models.json`` that points pi at an
  OpenAI-compatible endpoint (e.g. DB-GPT itself) instead of letting pi
  talk to external model services.
"""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

#: Platform guidance dropped into the isolated pi agent dir as AGENTS.md.
_PI_AGENTS_MD = """# DB-GPT platform guidance

- You run inside DB-GPT as a data agent. The platform tools (sql_query,
  code_interpreter, shell_interpreter, html_interpreter, web_search,
  web_fetch, question, todowrite, skill family) are the sanctioned way to
  touch data, code, files and the web.
- Web research rule: for questions about the external world that are
  time-sensitive or verifiable (products, comparisons, prices, versions,
  documentation, news, "what exists / which solutions" style questions),
  call web_search FIRST and ground the answer in its results; use web_fetch
  to read a candidate page in full when snippets are not enough. Do not
  answer such questions from memory alone.
- 涉及外部世界的时效性/可验证问题(产品、对比、价格、版本、文档、新闻、
  "有哪些方案"类),必须先调用 web_search 并基于结果回答,必要时用 web_fetch
  读全文;不得仅凭记忆作答。
- Plan multi-step work with todowrite; keep only one task in_progress.
"""

#: Default tool convergence: pi has no built-in sandbox, so execution-class
#: built-ins are disabled by default; anything the agent really needs to
#: execute should be routed through DB-GPT tools (sandboxed/audited).
DEFAULT_EXCLUDED_TOOLS = ["bash", "edit", "write"]

#: pi built-in tools (0.74.x). Used to emulate tool exclusion through the
#: ``--tools`` allowlist on CLI versions that lack ``--exclude-tools``.
KNOWN_PI_BUILTIN_TOOLS = ("read", "bash", "edit", "write")

#: Cached ``pi --help`` output per launcher argv (probe once per process).
_PI_HELP_CACHE: Dict[str, Optional[str]] = {}


def _pi_help_text(launcher: List[str]) -> Optional[str]:
    """Return the CLI's help output (cached), None on probe failure."""
    key = "\x00".join(launcher)
    if key in _PI_HELP_CACHE:
        return _PI_HELP_CACHE[key]
    text: Optional[str] = None
    try:
        out = subprocess.run(
            launcher + ["--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        text = out.stdout or out.stderr
    except Exception:
        logger.warning("pi harness: --help probe failed", exc_info=True)
    _PI_HELP_CACHE[key] = text
    return text


@dataclass
class PiHarnessConfig:
    """Spawn/behavior configuration for pi RPC child processes.

    All fields are optional and fall back to environment discovery, so an
    operator can override everything from ``configs/*.toml`` later without
    code changes.
    """

    #: pi CLI executable (path to ``cli.js`` via node, or plain ``pi``).
    pi_cli: Optional[str] = None
    #: Node binary used when ``pi_cli`` points at a JS entry.
    node_path: Optional[str] = None
    #: Working directory handed to pi (session-scoped workspace).
    cwd: Optional[str] = None
    #: Isolated pi agent directory (``PI_CODING_AGENT_DIR``). When set, pi
    #: reads settings/models/auth from here instead of ``~/.pi/agent``.
    agent_dir: Optional[str] = None
    #: Enable pi session files (persisted under ``session_dir``).
    enable_session: bool = False
    session_dir: Optional[str] = None

    #: Model selection passed to the CLI.
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    #: When set, an isolated agent dir is bootstrapped with a ``models.json``
    #: pointing at this compatible endpoint (e.g. DB-GPT itself).
    model_api_base: Optional[str] = None
    #: Wire API the endpoint speaks: ``openai-completions`` or
    #: ``anthropic-messages`` (see pi ``models.json`` docs).
    model_api: str = "openai-completions"
    #: Env var name used for ``$NAME`` interpolation inside models.json.
    api_key_env: str = "DBGPT_HARNESS_MODEL_API_KEY"

    #: Built-in tool names to disable (execution containment).
    excluded_tools: List[str] = field(
        default_factory=lambda: list(DEFAULT_EXCLUDED_TOOLS)
    )
    #: Extra tool names appended to the ``--tools`` allowlist when the
    #: exclusion emulation is active (e.g. DB-GPT tools registered by
    #: the bridged pi extension — the allowlist applies to extension
    #: tools too, so they must be listed explicitly).
    tool_allowlist_extra: List[str] = field(default_factory=list)
    #: Extra CLI args appended verbatim.
    extra_args: List[str] = field(default_factory=list)
    #: Extra environment variables merged into the child env (used by
    #: the DB-GPT tool bridge to hand the extension its manifest and
    #: loopback endpoint credentials).
    extra_env: Dict[str, str] = field(default_factory=dict)
    #: Args prepended to the argv (test doubles / env wrappers).
    command_prefix: List[str] = field(default_factory=list)

    #: Seconds without RPC traffic before a child is reaped (<=0 disables).
    idle_timeout_s: float = 1800.0
    #: Timeout for a single prompt run (<=0 disables).
    run_timeout_s: float = 1800.0
    #: Timeout for correlating a single command response.
    command_timeout_s: float = 60.0

    def resolve_command(self) -> List[str]:
        """Build the pi RPC command argv."""
        launcher: List[str] = list(self.command_prefix)
        pi_cli = self.pi_cli or os.environ.get("DBGPT_HARNESS_PI_CLI") or "pi"
        if pi_cli.endswith((".js", ".mjs", ".cjs")):
            node = self.node_path or shutil.which("node") or "node"
            launcher += [node, pi_cli]
        else:
            launcher += [pi_cli]
        argv: List[str] = list(launcher)
        argv += ["--mode", "rpc"]
        if not self.enable_session:
            argv.append("--no-session")
        elif self.session_dir:
            argv += ["--session-dir", self.session_dir]
        if self.excluded_tools:
            help_text = _pi_help_text(launcher) or ""
            if "--exclude-tools" in help_text:
                for tool in self.excluded_tools:
                    argv += ["--exclude-tools", tool]
            else:
                # pi <= 0.74.x has no --exclude-tools: emulate exclusion via
                # the --tools allowlist (known built-ins minus excluded);
                # fall back to --no-builtin-tools when nothing remains.
                allowed = [
                    tool
                    for tool in KNOWN_PI_BUILTIN_TOOLS
                    if tool not in self.excluded_tools
                ]
                allowed += [name for name in self.tool_allowlist_extra if name]
                if allowed:
                    argv += ["--tools", ",".join(allowed)]
                else:
                    argv.append("--no-builtin-tools")
        if self.provider:
            argv += ["--provider", self.provider]
        if self.model:
            argv += ["--model", self.model]
        if self.api_key:
            argv += ["--api-key", self.api_key]
        argv += list(self.extra_args)
        return argv

    def build_env(self) -> Dict[str, str]:
        """Environment for the pi child process."""
        env = dict(os.environ)
        if self.agent_dir:
            env["PI_CODING_AGENT_DIR"] = self.agent_dir
        env.update(self.extra_env)
        return env

    def prepare_agent_dir(self) -> None:
        """Bootstrap an isolated agent dir when ``model_api_base`` is set.

        Writes ``<agent_dir>/models.json`` declaring one provider whose
        ``baseUrl`` points at ``model_api_base`` and whose API key comes
        from ``$<api_key_env>`` (interpolated by pi at request time), so
        the key never lands on disk. Also injects the env var into
        :meth:`build_env` output.
        """
        if not self.model_api_base:
            return
        agent_dir = self.agent_dir
        if not agent_dir:
            if self.cwd:
                agent_dir = os.path.join(self.cwd, ".pi-agent")
            else:
                raise ValueError("model_api_base requires agent_dir or cwd to be set")
            self.agent_dir = agent_dir
        os.makedirs(agent_dir, exist_ok=True)
        models: List[Dict[str, str]] = []
        if self.model:
            models.append({"id": self.model})
        endpoint = {
            "baseUrl": self.model_api_base,
            "api": self.model_api,
            "apiKey": f"${self.api_key_env}",
        }
        if self.api_key:
            endpoint["apiKey"] = self.api_key
        if models:
            endpoint["models"] = models  # type: ignore[assignment]
        models_json = {"$schema": "https://pi.dev/schemas/models.schema.json"}
        models_json["providers"] = {"dbgpt": endpoint}
        path = os.path.join(agent_dir, "models.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(models_json, f, indent=2, ensure_ascii=False)
        logger.info("pi harness: wrote %s", path)
        agents_md = os.path.join(agent_dir, "AGENTS.md")
        with open(agents_md, "w", encoding="utf-8") as f:
            f.write(_PI_AGENTS_MD)

        # pi's RPC mode requires a user-level settings.json
        # to exist (even if empty) before it will process
        # prompts — it silently idles otherwise.
        settings_path = os.path.join(agent_dir, "settings.json")
        if not os.path.exists(settings_path):
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump({"$schema": "https://pi.dev/schemas/settings.schema.json"}, f)
            logger.info("pi harness: wrote %s", settings_path)
