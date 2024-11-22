import functools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from enum import Enum
from typing import Callable, List, Optional, Tuple
from urllib.parse import quote, urlparse

import setuptools
from setuptools import find_packages

with open("README.md", mode="r", encoding="utf-8") as fh:
    long_description = fh.read()

IS_DEV_MODE = os.getenv("IS_DEV_MODE", "true").lower() == "true"
# If you modify the version, please modify the version in the following files:
# dbgpt/_version.py
DB_GPT_VERSION = os.getenv("DB_GPT_VERSION", "0.6.2")

BUILD_NO_CACHE = os.getenv("BUILD_NO_CACHE", "true").lower() == "true"
LLAMA_CPP_GPU_ACCELERATION = (
    os.getenv("LLAMA_CPP_GPU_ACCELERATION", "true").lower() == "true"
)
BUILD_FROM_SOURCE = os.getenv("BUILD_FROM_SOURCE", "false").lower() == "true"
BUILD_FROM_SOURCE_URL_FAST_CHAT = os.getenv(
    "BUILD_FROM_SOURCE_URL_FAST_CHAT", "git+https://github.com/lm-sys/FastChat.git"
)
BUILD_VERSION_OPENAI = os.getenv("BUILD_VERSION_OPENAI")
INCLUDE_QUANTIZATION = os.getenv("INCLUDE_QUANTIZATION", "true").lower() == "true"
INCLUDE_OBSERVABILITY = os.getenv("INCLUDE_OBSERVABILITY", "true").lower() == "true"


def parse_requirements(file_name: str) -> List[str]:
    with open(file_name) as f:
        return [
            require.strip()
            for require in f
            if require.strip() and not require.startswith("#")
        ]


def find_python():
    python_path = sys.executable
    print(python_path)
    if not python_path:
        print("Python command not found.")
        return None
    return python_path


def get_latest_version(package_name: str, index_url: str, default_version: str):
    python_command = find_python()
    if not python_command:
        print("Python command not found.")
        return default_version

    command_index_versions = [
        python_command,
        "-m",
        "pip",
        "index",
        "versions",
        package_name,
        "--index-url",
        index_url,
    ]

    result_index_versions = subprocess.run(
        command_index_versions, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result_index_versions.returncode == 0:
        output = result_index_versions.stdout.decode()
        lines = output.split("\n")
        for line in lines:
            if "Available versions:" in line:
                available_versions = line.split(":")[1].strip()
                latest_version = available_versions.split(",")[0].strip()
                # Query for compatibility with the latest version of torch
                if package_name == "torch" or "torchvision":
                    latest_version = latest_version.split("+")[0]
                return latest_version
    else:
        command_simulate_install = [
            python_command,
            "-m",
            "pip",
            "install",
            f"{package_name}==",
        ]

        result_simulate_install = subprocess.run(
            command_simulate_install, stderr=subprocess.PIPE
        )
        print(result_simulate_install)
        stderr_output = result_simulate_install.stderr.decode()
        print(stderr_output)
        match = re.search(r"from versions: (.+?)\)", stderr_output)
        if match:
            available_versions = match.group(1).split(", ")
            latest_version = available_versions[-1].strip()
            return latest_version
    return default_version


def encode_url(package_url: str) -> str:
    parsed_url = urlparse(package_url)
    encoded_path = quote(parsed_url.path)
    safe_url = parsed_url._replace(path=encoded_path).geturl()
    return safe_url, parsed_url.path


def cache_package(package_url: str, package_name: str, is_windows: bool = False):
    safe_url, parsed_url = encode_url(package_url)
    if BUILD_NO_CACHE:
        return safe_url

    from pip._internal.utils.appdirs import user_cache_dir

    filename = os.path.basename(parsed_url)
    cache_dir = os.path.join(user_cache_dir("pip"), "http", "wheels", package_name)
    os.makedirs(cache_dir, exist_ok=True)

    local_path = os.path.join(cache_dir, filename)
    if not os.path.exists(local_path):
        temp_path = local_path + ".tmp"
        if os.path.exists(temp_path):
            os.remove(temp_path)
        try:
            print(f"Download {safe_url} to {local_path}")
            urllib.request.urlretrieve(safe_url, temp_path)
            shutil.move(temp_path, local_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    return f"file:///{local_path}" if is_windows else f"file://{local_path}"


class SetupSpec:
    def __init__(self) -> None:
        self.extras: dict = {}
        self.install_requires: List[str] = []

    @property
    def unique_extras(self) -> dict[str, list[str]]:
        unique_extras = {}
        for k, v in self.extras.items():
            unique_extras[k] = list(set(v))
        return unique_extras


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


@functools.cache
def get_cpu_avx_support() -> Tuple[OSType, AVXType]:
    system = platform.system()
    os_type = OSType.OTHER
    cpu_avx = AVXType.BASIC
    env_cpu_avx = AVXType.of_type(os.getenv("DBGPT_LLAMA_CPP_AVX"))

    if "windows" in system.lower():
        os_type = OSType.WINDOWS
        output = "avx2"
        print("Current platform is windows, use avx2 as default cpu architecture")
    elif system == "Linux":
        os_type = OSType.LINUX
        if os.path.exists("/etc/alpine-release"):
            # For Alpine, we'll check /proc/cpuinfo directly
            with open("/proc/cpuinfo", "r") as f:
                output = f.read()
        else:
            result = subprocess.run(
                ["lscpu"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            output = result.stdout.decode()
    elif system == "Darwin":
        os_type = OSType.DARWIN
        result = subprocess.run(
            ["sysctl", "-a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = result.stdout.decode()
    else:
        os_type = OSType.OTHER
        print("Unsupported OS to get cpu avx, use default")
        return os_type, env_cpu_avx if env_cpu_avx else cpu_avx

    if "avx512" in output.lower():
        cpu_avx = AVXType.AVX512
    elif "avx2" in output.lower():
        cpu_avx = AVXType.AVX2
    elif "avx " in output.lower():
        # cpu_avx =  AVXType.AVX
        pass
    return os_type, env_cpu_avx if env_cpu_avx else cpu_avx


def get_cuda_version_from_torch():
    try:
        import torch

        return torch.version.cuda
    except:
        return None


def get_cuda_version_from_nvcc():
    try:
        output = subprocess.check_output(["nvcc", "--version"])
        version_line = [
            line for line in output.decode("utf-8").split("\n") if "release" in line
        ][0]
        return version_line.split("release")[-1].strip().split(",")[0]
    except:
        return None


def get_cuda_version_from_nvidia_smi():
    try:
        output = subprocess.check_output(["nvidia-smi"]).decode("utf-8")
        match = re.search(r"CUDA Version:\s+(\d+\.\d+)", output)
        if match:
            return match.group(1)
        else:
            return None
    except:
        return None


def get_cuda_version() -> str:
    try:
        cuda_version = get_cuda_version_from_torch()
        if not cuda_version:
            cuda_version = get_cuda_version_from_nvcc()
        if not cuda_version:
            cuda_version = get_cuda_version_from_nvidia_smi()
        return cuda_version
    except Exception:
        return None


def _build_wheels(
    pkg_name: str,
    pkg_version: str,
    base_url: str = None,
    base_url_func: Callable[[str, str, str], str] = None,
    pkg_file_func: Callable[[str, str, str, str, OSType], str] = None,
    supported_cuda_versions: List[str] = ["11.8", "12.1"],
) -> Optional[str]:
    """
    Build the URL for the package wheel file based on the package name, version, and CUDA version.
    Args:
        pkg_name (str): The name of the package.
        pkg_version (str): The version of the package.
        base_url (str): The base URL for downloading the package.
        base_url_func (Callable): A function to generate the base URL.
        pkg_file_func (Callable): build package file function.
            function params: pkg_name, pkg_version, cuda_version, py_version, OSType
        supported_cuda_versions (List[str]): The list of supported CUDA versions.
    Returns:
        Optional[str]: The URL for the package wheel file.
    """
    os_type, _ = get_cpu_avx_support()
    cuda_version = get_cuda_version()
    py_version = platform.python_version()
    py_version = "cp" + "".join(py_version.split(".")[0:2])
    if os_type == OSType.DARWIN or not cuda_version:
        return None

    if cuda_version in supported_cuda_versions:
        cuda_version = cuda_version
    else:
        print(
            f"Warning: Your CUDA version {cuda_version} is not in our set supported_cuda_versions , we will use our set version."
        )
        if cuda_version < "12.1":
            cuda_version = supported_cuda_versions[0]
        else:
            cuda_version = supported_cuda_versions[-1]

    cuda_version = "cu" + cuda_version.replace(".", "")
    os_pkg_name = "linux_x86_64" if os_type == OSType.LINUX else "win_amd64"
    if base_url_func:
        base_url = base_url_func(pkg_version, cuda_version, py_version)
        if base_url and base_url.endswith("/"):
            base_url = base_url[:-1]
    if pkg_file_func:
        full_pkg_file = pkg_file_func(
            pkg_name, pkg_version, cuda_version, py_version, os_type
        )
    else:
        full_pkg_file = f"{pkg_name}-{pkg_version}+{cuda_version}-{py_version}-{py_version}-{os_pkg_name}.whl"
    if not base_url:
        return full_pkg_file
    else:
        return f"{base_url}/{full_pkg_file}"


def torch_requires(
    torch_version: str = "2.2.1",
    torchvision_version: str = "0.17.1",
    torchaudio_version: str = "2.2.1",
):
    os_type, _ = get_cpu_avx_support()
    torch_pkgs = [
        f"torch=={torch_version}",
        f"torchvision=={torchvision_version}",
        f"torchaudio=={torchaudio_version}",
    ]
    # Initialize torch_cuda_pkgs for non-Darwin OSes;
    # it will be the same as torch_pkgs for Darwin or when no specific CUDA handling is needed
    torch_cuda_pkgs = torch_pkgs[:]

    if os_type != OSType.DARWIN:
        supported_versions = ["11.8", "12.1"]
        base_url_func = lambda v, x, y: f"https://download.pytorch.org/whl/{x}"
        torch_url = _build_wheels(
            "torch",
            torch_version,
            base_url_func=base_url_func,
            supported_cuda_versions=supported_versions,
        )
        torchvision_url = _build_wheels(
            "torchvision",
            torchvision_version,
            base_url_func=base_url_func,
            supported_cuda_versions=supported_versions,
        )

        # Cache and add CUDA-dependent packages if URLs are available
        if torch_url:
            torch_url_cached = cache_package(
                torch_url, "torch", os_type == OSType.WINDOWS
            )
            torch_cuda_pkgs[0] = f"torch @ {torch_url_cached}"
        if torchvision_url:
            torchvision_url_cached = cache_package(
                torchvision_url, "torchvision", os_type == OSType.WINDOWS
            )
            torch_cuda_pkgs[1] = f"torchvision @ {torchvision_url_cached}"

    # Assuming 'setup_spec' is a dictionary where we're adding these dependencies
    setup_spec.extras["torch"] = torch_pkgs
    setup_spec.extras["torch_cpu"] = torch_pkgs
    setup_spec.extras["torch_cuda"] = torch_cuda_pkgs


def llama_cpp_python_cuda_requires():
    cuda_version = get_cuda_version()
    supported_cuda_versions = ["11.8", "12.1"]
    device = "cpu"
    if not cuda_version:
        print("CUDA not support, use cpu version")
        return
    if not LLAMA_CPP_GPU_ACCELERATION:
        print("Disable GPU acceleration")
        return
    # Supports GPU acceleration
    if cuda_version <= "11.8" and not None:
        device = "cu" + supported_cuda_versions[0].replace(".", "")
    else:
        device = "cu" + supported_cuda_versions[-1].replace(".", "")
    os_type, cpu_avx = get_cpu_avx_support()
    print(f"OS: {os_type}, cpu avx: {cpu_avx}")
    supported_os = [OSType.WINDOWS, OSType.LINUX]
    if os_type not in supported_os:
        print(
            f"llama_cpp_python_cuda just support in os: {[r._value_ for r in supported_os]}"
        )
        return
    cpu_device = ""
    if cpu_avx == AVXType.AVX2 or cpu_avx == AVXType.AVX512:
        cpu_device = "avx"
    else:
        cpu_device = "basic"
    device += cpu_device
    base_url = "https://github.com/jllllll/llama-cpp-python-cuBLAS-wheels/releases/download/textgen-webui"
    llama_cpp_version = "0.2.26"
    py_version = "cp310"
    os_pkg_name = "manylinux_2_31_x86_64" if os_type == OSType.LINUX else "win_amd64"
    extra_index_url = f"{base_url}/llama_cpp_python_cuda-{llama_cpp_version}+{device}-{py_version}-{py_version}-{os_pkg_name}.whl"
    extra_index_url, _ = encode_url(extra_index_url)
    print(f"Install llama_cpp_python_cuda from {extra_index_url}")

    setup_spec.extras["llama_cpp"].append(f"llama_cpp_python_cuda @ {extra_index_url}")


def core_requires():
    """
    pip install dbgpt or pip install "dbgpt[core]"
    """
    setup_spec.extras["core"] = [
        "aiohttp==3.8.4",
        "chardet==5.1.0",
        "importlib-resources==5.12.0",
        "python-dotenv==1.0.0",
        "cachetools",
        "pydantic>=2.6.0",
        # For AWEL type checking
        "typeguard",
        # Snowflake no additional dependencies.
        "snowflake-id",
        "typing_inspect",
    ]
    # For DB-GPT python client SDK
    setup_spec.extras["client"] = setup_spec.extras["core"] + [
        "httpx",
        "fastapi>=0.100.0",
        # For retry, chromadb need tenacity<=8.3.0
        "tenacity<=8.3.0",
    ]
    # Simple command line dependencies
    setup_spec.extras["cli"] = setup_spec.extras["client"] + [
        "prettytable",
        "click",
        "psutil==5.9.4",
        "colorama==0.4.6",
        "tomlkit",
        "rich",
    ]
    # Agent dependencies
    setup_spec.extras["agent"] = setup_spec.extras["cli"] + [
        "termcolor",
        # https://github.com/eosphoros-ai/DB-GPT/issues/551
        # TODO: remove pandas dependency
        # alpine can't install pandas by default
        "pandas==2.0.3",
        # numpy should less than 2.0.0
        "numpy>=1.21.0,<2.0.0",
    ]

    # Just use by DB-GPT internal, we should find the smallest dependency set for run
    # we core unit test.
    # The dependency "framework" is too large for now.
    setup_spec.extras["simple_framework"] = setup_spec.extras["agent"] + [
        "jinja2",
        "uvicorn",
        "shortuuid",
        # 2.0.29 not support duckdb now
        "SQLAlchemy>=2.0.25, <2.0.29",
        # for cache
        "msgpack",
        # for AWEL operator serialization
        "cloudpickle",
        # for cache
        # TODO: pympler has not been updated for a long time and needs to
        #  find a new toolkit.
        "pympler",
        "duckdb",
        "duckdb-engine==0.9.1",
        # lightweight python library for scheduling jobs
        "schedule",
        # For datasource subpackage
        "sqlparse==0.4.4",
    ]
    # TODO: remove fschat from simple_framework
    if BUILD_FROM_SOURCE:
        setup_spec.extras["simple_framework"].append(
            f"fschat @ {BUILD_FROM_SOURCE_URL_FAST_CHAT}"
        )
    else:
        setup_spec.extras["simple_framework"].append("fschat")

    setup_spec.extras["framework"] = setup_spec.extras["simple_framework"] + [
        "coloredlogs",
        "seaborn",
        "auto-gpt-plugin-template",
        "gTTS==2.3.1",
        "pymysql",
        "jsonschema",
        # TODO move transformers to default
        # "transformers>=4.31.0",
        "transformers>=4.34.0",
        "alembic==1.12.0",
        # for excel
        "openpyxl==3.1.2",
        "chardet==5.1.0",
        "xlrd==2.0.1",
        "aiofiles",
        # for agent
        "GitPython",
        # For AWEL dag visualization, graphviz is a small package, also we can move it to default.
        "graphviz",
        # For security
        "cryptography",
        # For high performance RPC communication in code execution
        "pyzmq",
    ]


def code_execution_requires():
    """
    pip install "dbgpt[code]"

    Code execution dependencies.
    """
    setup_spec.extras["code"] = setup_spec.extras["core"] + [
        "msgpack",
        # for AWEL operator serialization
        "cloudpickle",
        "lyric-py>=0.1.4",
        "lyric-py-worker>=0.1.4",
        "lyric-js-worker>=0.1.4",
    ]


def knowledge_requires():
    """
    pip install "dbgpt[rag]"
    """
    setup_spec.extras["rag"] = setup_spec.extras["vstore"] + [
        "spacy==3.7",
        "markdown",
        "bs4",
        "python-pptx",
        "python-docx",
        "pypdf",
        "pdfplumber",
        "python-multipart",
        "sentence-transformers",
    ]

    setup_spec.extras["graph_rag"] = setup_spec.extras["rag"] + [
        "neo4j",
        "dbgpt-tugraph-plugins>=0.1.0rc1",
    ]


def llama_cpp_requires():
    """
    pip install "dbgpt[llama_cpp]"
    """
    setup_spec.extras["llama_cpp"] = ["llama-cpp-python"]
    llama_cpp_python_cuda_requires()


def _build_autoawq_requires() -> Optional[str]:
    os_type, _ = get_cpu_avx_support()
    if os_type == OSType.DARWIN:
        return None
    return "auto-gptq"


def quantization_requires():
    os_type, _ = get_cpu_avx_support()
    quantization_pkgs = []
    if os_type == OSType.WINDOWS:
        # For Windows, fetch a specific bitsandbytes WHL package
        latest_version = get_latest_version(
            "bitsandbytes",
            "https://jllllll.github.io/bitsandbytes-windows-webui",
            "0.41.1",
        )
        whl_url = f"https://github.com/jllllll/bitsandbytes-windows-webui/releases/download/wheels/bitsandbytes-{latest_version}-py3-none-win_amd64.whl"
        local_pkg_path = cache_package(whl_url, "bitsandbytes", True)
        setup_spec.extras["bitsandbytes"] = [f"bitsandbytes @ {local_pkg_path}"]
    else:
        setup_spec.extras["bitsandbytes"] = ["bitsandbytes"]

    if os_type != OSType.DARWIN:
        # Since transformers 4.35.0, the GPT-Q/AWQ model can be loaded using AutoModelForCausalLM.
        # autoawq requirements:
        # 1. Compute Capability 7.5 (sm75). Turing and later architectures are supported.
        # 2. CUDA Toolkit 11.8 and later.
        cuda_version = get_cuda_version()
        # autoawq_latest_version = get_latest_version("autoawq", "", "0.2.4")
        if cuda_version is None or cuda_version == "12.1":
            quantization_pkgs.extend(["autoawq", _build_autoawq_requires(), "optimum"])
        else:
            # TODO(yyhhyy): Add autoawq install method for CUDA version 11.8
            quantization_pkgs.extend(["autoawq", _build_autoawq_requires(), "optimum"])

    setup_spec.extras["quantization"] = (
        ["cpm_kernels"] + quantization_pkgs + setup_spec.extras["bitsandbytes"]
    )


def all_vector_store_requires():
    """
    pip install "dbgpt[vstore]"
    """
    setup_spec.extras["vstore"] = [
        "chromadb>=0.4.22",
    ]
    setup_spec.extras["vstore_weaviate"] = setup_spec.extras["vstore"] + [
        # "protobuf",
        # "grpcio",
        # weaviate depends on grpc which version is very low, we should install it
        # manually.
        "weaviate-client",
    ]
    setup_spec.extras["vstore_milvus"] = setup_spec.extras["vstore"] + [
        "pymilvus",
    ]
    setup_spec.extras["vstore_all"] = (
        setup_spec.extras["vstore"]
        + setup_spec.extras["vstore_weaviate"]
        + setup_spec.extras["vstore_milvus"]
    )


def all_datasource_requires():
    """
    pip install "dbgpt[datasource]"
    """
    setup_spec.extras["datasource"] = [
        # "sqlparse==0.4.4",
        "pymysql",
    ]
    # If you want to install psycopg2 and mysqlclient in ubuntu, you should install
    # libpq-dev and libmysqlclient-dev first.
    setup_spec.extras["datasource_all"] = setup_spec.extras["datasource"] + [
        "pyspark",
        "pymssql",
        # install psycopg2-binary when you are in a virtual environment
        # pip install psycopg2-binary
        "psycopg2",
        # mysqlclient 2.2.x have pkg-config issue on 3.10+
        "mysqlclient==2.1.0",
        # pydoris is too old, we should find a new package to replace it.
        "pydoris>=1.0.2,<2.0.0",
        "clickhouse-connect",
        "pyhive",
        "thrift",
        "thrift_sasl",
        "vertica_python",
    ]


def openai_requires():
    """
    pip install "dbgpt[openai]"
    """
    setup_spec.extras["openai"] = ["tiktoken"]
    if BUILD_VERSION_OPENAI:
        # Read openai sdk version from env
        setup_spec.extras["openai"].append(f"openai=={BUILD_VERSION_OPENAI}")
    else:
        setup_spec.extras["openai"].append("openai")

    if INCLUDE_OBSERVABILITY:
        setup_spec.extras["openai"] += setup_spec.extras["observability"]

    setup_spec.extras["openai"] += setup_spec.extras["framework"]
    setup_spec.extras["openai"] += setup_spec.extras["rag"]


def gpt4all_requires():
    """
    pip install "dbgpt[gpt4all]"
    """
    setup_spec.extras["gpt4all"] = ["gpt4all"]


def vllm_requires():
    """
    pip install "dbgpt[vllm]"
    """
    setup_spec.extras["vllm"] = ["vllm"]


def cache_requires():
    """
    pip install "dbgpt[cache]"
    """
    setup_spec.extras["cache"] = ["rocksdict"]


def observability_requires():
    """
    pip install "dbgpt[observability]"

    Send DB-GPT traces to OpenTelemetry compatible backends.
    """
    setup_spec.extras["observability"] = [
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp",
    ]


def default_requires():
    """
    pip install "dbgpt[default]"
    """
    setup_spec.extras["default"] = [
        # "tokenizers==0.13.3",
        "tokenizers>=0.14",
        "accelerate>=0.20.3",
        "zhipuai",
        "dashscope",
        "chardet",
        "sentencepiece",
        "ollama",
        "qianfan",
        "libro>=0.1.25",
        "poetry",
    ]
    setup_spec.extras["default"] += setup_spec.extras["framework"]
    setup_spec.extras["default"] += setup_spec.extras["rag"]
    setup_spec.extras["default"] += setup_spec.extras["graph_rag"]
    setup_spec.extras["default"] += setup_spec.extras["datasource"]
    setup_spec.extras["default"] += setup_spec.extras["torch"]
    setup_spec.extras["default"] += setup_spec.extras["cache"]
    setup_spec.extras["default"] += setup_spec.extras["code"]
    if INCLUDE_QUANTIZATION:
        # Add quantization extra to default, default is True
        setup_spec.extras["default"] += setup_spec.extras["quantization"]
    if INCLUDE_OBSERVABILITY:
        setup_spec.extras["default"] += setup_spec.extras["observability"]


def all_requires():
    requires = set()
    for _, pkgs in setup_spec.extras.items():
        for pkg in pkgs:
            requires.add(pkg)
    setup_spec.extras["all"] = list(requires)


def init_install_requires():
    setup_spec.install_requires += setup_spec.extras["core"]
    print(f"Install requires: \n{','.join(setup_spec.install_requires)}")


core_requires()
code_execution_requires()
torch_requires()
llama_cpp_requires()
quantization_requires()

all_vector_store_requires()
all_datasource_requires()
knowledge_requires()
gpt4all_requires()
vllm_requires()
cache_requires()
observability_requires()

openai_requires()
# must be last
default_requires()
all_requires()
init_install_requires()

# Packages to exclude when IS_DEV_MODE is False
excluded_packages = ["tests", "*.tests", "*.tests.*", "examples"]

if IS_DEV_MODE:
    packages = find_packages(exclude=excluded_packages)
else:
    packages = find_packages(
        exclude=excluded_packages,
        include=[
            "dbgpt",
            "dbgpt._private",
            "dbgpt._private.*",
            "dbgpt.agent",
            "dbgpt.agent.*",
            "dbgpt.cli",
            "dbgpt.cli.*",
            "dbgpt.client",
            "dbgpt.client.*",
            "dbgpt.configs",
            "dbgpt.configs.*",
            "dbgpt.core",
            "dbgpt.core.*",
            "dbgpt.datasource",
            "dbgpt.datasource.*",
            "dbgpt.experimental",
            "dbgpt.experimental.*",
            "dbgpt.model",
            "dbgpt.model.proxy",
            "dbgpt.model.proxy.*",
            "dbgpt.model.operators",
            "dbgpt.model.operators.*",
            "dbgpt.model.utils",
            "dbgpt.model.utils.*",
            "dbgpt.model.adapter",
            "dbgpt.rag",
            "dbgpt.rag.*",
            "dbgpt.storage",
            "dbgpt.storage.*",
            "dbgpt.util",
            "dbgpt.util.*",
            "dbgpt.vis",
            "dbgpt.vis.*",
        ],
    )


class PrintExtrasCommand(setuptools.Command):
    description = "print extras_require"
    user_options = [
        ("output=", "o", "Path to output the extras_require JSON"),
    ]

    def initialize_options(self):
        self.output = None

    def finalize_options(self):
        if self.output is None:
            raise ValueError("output is not set")

    def run(self):
        with open(self.output, "w") as f:
            json.dump(setup_spec.unique_extras, f, indent=2)


setuptools.setup(
    name="dbgpt",
    packages=packages,
    version=DB_GPT_VERSION,
    author="csunny",
    author_email="cfqcsunny@gmail.com",
    description="DB-GPT is an experimental open-source project that uses localized GPT "
    "large models to interact with your data and environment."
    " With this solution, you can be assured that there is no risk of data leakage, "
    "and your data is 100% private and secure.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=setup_spec.install_requires,
    url="https://github.com/eosphoros-ai/DB-GPT",
    license="https://opensource.org/license/mit/",
    python_requires=">=3.10",
    extras_require=setup_spec.unique_extras,
    cmdclass={
        "print_extras": PrintExtrasCommand,
    },
    entry_points={
        "console_scripts": [
            "dbgpt=dbgpt.cli.cli_scripts:main",
        ],
    },
)
