import os

LANGUAGE_IMAGES = {
    "python": "python:3.11-slim",
    "python-vnc": "vnc-gui-browser:latest",
    "javascript": "node:18-slim",
    "java": "openjdk:11-jre-slim",
    "cpp": "gcc:latest",
    "go": "golang:1.21-alpine",
    "rust": "rust:1.75-slim",
}

WORKING_DIR = "/workspace"


def get_command_by_language(language: str, filename: str) -> str:
    commands = {
        "python-vnc": f"python3 {filename}",
        "python": f"python {filename}",
        "javascript": f"node {filename}",
        "java": f"javac {filename} && java {filename[:-5]}",
        "cpp": f"g++ -o program {filename} && ./program",
        "go": f"go run {filename}",
        "rust": f"rustc {filename} -o program && ./program",
    }
    return commands.get(language, f"cat {filename}")


MAX_MEMORY = 256 * 1024 * 1024  # 256MB
MAX_CPU_PERCENT = 50.0
MAX_EXECUTION_TIME = 30  # seconds
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DEPENDENCY_INSTALL_TIME = 300  # seconds
MAX_DEPENDENCY_INSTALL_SIZE = 200 * 1024 * 1024  # 200MB
MAX_PROCESSES = 10


SANDBOX_RUNTIME = os.getenv(
    "SANDBOX_RUNTIME", "local"
)  # Optional values: docker, podman, nerdctl, local
