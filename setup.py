from typing import List, Tuple

import setuptools
import platform
import subprocess
import os
from enum import Enum

from setuptools import find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()


def parse_requirements(file_name: str) -> List[str]:
    with open(file_name) as f:
        return [
            require.strip()
            for require in f
            if require.strip() and not require.startswith("#")
        ]


class SetupSpec:
    def __init__(self) -> None:
        self.extras: dict = {}


setup_spec = SetupSpec()


class AVXType(Enum):
    BASIC = "basic"
    AVX = "AVX"
    AVX2 = "AVX2"
    AVX512 = "AVX512"

    @staticmethod
    def of_type(avx: str):
        for item in AVXType:
            if item._value_ == avx:
                return item
        return None


class OSType(Enum):
    WINDOWS = "win"
    LINUX = "linux"
    DARWIN = "darwin"
    OTHER = "other"


def get_cpu_avx_support() -> Tuple[OSType, AVXType]:
    system = platform.system()
    os_type = OSType.OTHER
    cpu_avx = AVXType.BASIC
    env_cpu_avx = AVXType.of_type(os.getenv("DBGPT_LLAMA_CPP_AVX"))

    cmds = ["lscpu"]
    if system == "Windows":
        cmds = ["coreinfo"]
        os_type = OSType.WINDOWS
    elif system == "Linux":
        cmds = ["lscpu"]
        os_type = OSType.LINUX
    elif system == "Darwin":
        cmds = ["sysctl", "-a"]
        os_type = OSType.DARWIN
    else:
        os_type = OSType.OTHER
        print("Unsupported OS to get cpu avx, use default")
        return os_type, env_cpu_avx if env_cpu_avx else cpu_avx
    result = subprocess.run(cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode()
    if "avx512" in output.lower():
        cpu_avx = AVXType.AVX512
    elif "avx2" in output.lower():
        cpu_avx = AVXType.AVX2
    elif "avx " in output.lower():
        # cpu_avx =  AVXType.AVX
        pass
    return os_type, env_cpu_avx if env_cpu_avx else cpu_avx


def get_cuda_version() -> str:
    try:
        import torch

        return torch.version.cuda
    except Exception:
        return None


def llama_cpp_python_cuda_requires():
    cuda_version = get_cuda_version()
    device = "cpu"
    if not cuda_version:
        print("CUDA not support, use cpu version")
        return
    device = "cu" + cuda_version.replace(".", "")
    os_type, cpu_avx = get_cpu_avx_support()
    supported_os = [OSType.WINDOWS, OSType.LINUX]
    if os_type not in supported_os:
        print(
            f"llama_cpp_python_cuda just support in os: {[r._value_ for r in supported_os]}"
        )
        return
    cpu_avx = cpu_avx._value_
    base_url = "https://github.com/jllllll/llama-cpp-python-cuBLAS-wheels/releases/download/textgen-webui"
    llama_cpp_version = "0.1.77"
    py_version = "cp310"
    os_pkg_name = "linux_x86_64" if os_type == OSType.LINUX else "win_amd64"
    extra_index_url = f"{base_url}/llama_cpp_python_cuda-{llama_cpp_version}+{device}{cpu_avx}-{py_version}-{py_version}-{os_pkg_name}.whl"
    print(f"Install llama_cpp_python_cuda from {extra_index_url}")

    setup_spec.extras["llama_cpp"].append(f"llama_cpp_python_cuda @ {extra_index_url}")


def llama_cpp_requires():
    """
    pip install "db-gpt[llama_cpp]"
    """
    setup_spec.extras["llama_cpp"] = ["llama-cpp-python"]
    llama_cpp_python_cuda_requires()


def all_vector_store_requires():
    """
    pip install "db-gpt[vstore]"
    """
    setup_spec.extras["vstore"] = [
        "grpcio==1.47.5",  # maybe delete it
        "pymilvus==2.2.1",
    ]


def all_datasource_requires():
    """
    pip install "db-gpt[datasource]"
    """
    setup_spec.extras["datasource"] = ["pymssql", "pymysql"]


def all_requires():
    requires = set()
    for _, pkgs in setup_spec.extras.items():
        for pkg in pkgs:
            requires.add(pkg)
    setup_spec.extras["all"] = list(requires)


llama_cpp_requires()
all_vector_store_requires()
all_datasource_requires()

# must be last
all_requires()

setuptools.setup(
    name="db-gpt",
    packages=find_packages(exclude=("tests", "*.tests", "*.tests.*", "examples")),
    version="0.3.5",
    author="csunny",
    author_email="cfqcsunny@gmail.com",
    description="DB-GPT is an experimental open-source project that uses localized GPT large models to interact with your data and environment."
    " With this solution, you can be assured that there is no risk of data leakage, and your data is 100% private and secure.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=parse_requirements("requirements.txt"),
    url="https://github.com/eosphoros-ai/DB-GPT",
    license="https://opensource.org/license/mit/",
    python_requires=">=3.10",
    extras_require=setup_spec.extras,
    entry_points={
        "console_scripts": [
            "dbgpt_server=pilot.server:webserver",
        ],
    },
)
