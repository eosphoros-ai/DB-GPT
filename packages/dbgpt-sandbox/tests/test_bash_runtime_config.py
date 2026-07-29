from pathlib import Path

from dbgpt_sandbox.sandbox.config import (
    LANGUAGE_IMAGES,
    get_command_by_language,
)
from dbgpt_sandbox.sandbox.execution_layer.base import SessionConfig
from dbgpt_sandbox.sandbox.execution_layer.docker_runtime import (
    DockerSandboxSession,
)


def test_bash_reuses_python_slim_image():
    assert LANGUAGE_IMAGES["bash"] == LANGUAGE_IMAGES["python"]


def test_bash_executes_with_posix_shell():
    assert get_command_by_language("bash", "run.sh") == "sh run.sh"


def test_docker_bash_code_uses_shell_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dbgpt_sandbox.sandbox.execution_layer.docker_runtime.tempfile.gettempdir",
        lambda: str(tmp_path),
    )
    session = DockerSandboxSession(
        "bash-test",
        SessionConfig(language="bash"),
        docker_client=None,
    )

    code_file = Path(session._create_code_file("printf 'hello\\n'"))

    assert code_file.suffix == ".sh"
