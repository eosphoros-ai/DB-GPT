from typing import List, Tuple, Optional, Callable
import setuptools
import platform
import subprocess
import os
from enum import Enum
import urllib.request
from urllib.parse import urlparse, quote
import re
import shutil
from setuptools import find_packages
import functools

with open("README.md", mode="r", encoding="utf-8") as fh:
    long_description = fh.read()

BUILD_NO_CACHE = os.getenv("BUILD_NO_CACHE", "true").lower() == "true"
LLAMA_CPP_GPU_ACCELERATION = (
    os.getenv("LLAMA_CPP_GPU_ACCELERATION", "true").lower() == "true"
)
BUILD_FROM_SOURCE = os.getenv("BUILD_FROM_SOURCE", "false").lower() == "true"
BUILD_FROM_SOURCE_URL_FAST_CHAT = os.getenv(
    "BUILD_FROM_SOURCE_URL_FAST_CHAT", "git+https://github.com/lm-sys/FastChat.git"
)
BUILD_VERSION_OPENAI = os.getenv("BUILD_VERSION_OPENAI")


def parse_requirements(file_name: str) -> List[str]:
    with open(file_name) as f:
        return [
            require.strip()
            for require in f
            if require.strip() and not require.startswith("#")
        ]


def get_latest_version(package_name: str, index_url: str, default_version: str):
    python_command = shutil.which("python")
    if not python_command:
        python_command = shutil.which("python3")
        if not python_command:
            print("Python command not found.")
            return default_version

    command = [
        python_command,
        "-m",
        "pip",
        "index",
        "versions",
        package_name,
        "--index-url",
        index_url,
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print("Error executing command.")
        print(result.stderr.decode())
        return default_version

    output = result.stdout.decode()
    lines = output.split("\n")
    for line in lines:
        if "Available versions:" in line:
            available_versions = line.split(":")[1].strip()
            latest_version = available_versions.split(",")[0].strip()
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
    supported_cuda_versions: List[str] = ["11.7", "11.8"],
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
    if cuda_version not in supported_cuda_versions:
        print(
            f"Warnning: {pkg_name} supported cuda version: {supported_cuda_versions}, replace to {supported_cuda_versions[-1]}"
        )
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
    torch_version: str = "2.0.1",
    torchvision_version: str = "0.15.2",
    torchaudio_version: str = "2.0.2",
):
    torch_pkgs = [
        f"torch=={torch_version}",
        f"torchvision=={torchvision_version}",
        f"torchaudio=={torchaudio_version}",
    ]
    torch_cuda_pkgs = []
    os_type, _ = get_cpu_avx_support()
    if os_type != OSType.DARWIN:
        cuda_version = get_cuda_version()
        if cuda_version:
            supported_versions = ["11.7", "11.8"]
            # torch_url = f"https://download.pytorch.org/whl/{cuda_version}/torch-{torch_version}+{cuda_version}-{py_version}-{py_version}-{os_pkg_name}.whl"
            # torchvision_url = f"https://download.pytorch.org/whl/{cuda_version}/torchvision-{torchvision_version}+{cuda_version}-{py_version}-{py_version}-{os_pkg_name}.whl"
            torch_url = _build_wheels(
                "torch",
                torch_version,
                base_url_func=lambda v, x, y: f"https://download.pytorch.org/whl/{x}",
                supported_cuda_versions=supported_versions,
            )
            torchvision_url = _build_wheels(
                "torchvision",
                torchvision_version,
                base_url_func=lambda v, x, y: f"https://download.pytorch.org/whl/{x}",
                supported_cuda_versions=supported_versions,
            )
            torch_url_cached = cache_package(
                torch_url, "torch", os_type == OSType.WINDOWS
            )
            torchvision_url_cached = cache_package(
                torchvision_url, "torchvision", os_type == OSType.WINDOWS
            )

            torch_cuda_pkgs = [
                f"torch @ {torch_url_cached}",
                f"torchvision @ {torchvision_url_cached}",
                f"torchaudio=={torchaudio_version}",
            ]

    setup_spec.extras["torch"] = torch_pkgs
    setup_spec.extras["torch_cpu"] = torch_pkgs
    setup_spec.extras["torch_cuda"] = torch_cuda_pkgs


def llama_cpp_python_cuda_requires():
    cuda_version = get_cuda_version()
    device = "cpu"
    if not cuda_version:
        print("CUDA not support, use cpu version")
        return
    if not LLAMA_CPP_GPU_ACCELERATION:
        print("Disable GPU acceleration")
        return
    # Supports GPU acceleration
    device = "cu" + cuda_version.replace(".", "")
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
    llama_cpp_version = "0.2.10"
    py_version = "cp310"
    os_pkg_name = "manylinux_2_31_x86_64" if os_type == OSType.LINUX else "win_amd64"
    extra_index_url = f"{base_url}/llama_cpp_python_cuda-{llama_cpp_version}+{device}-{py_version}-{py_version}-{os_pkg_name}.whl"
    extra_index_url, _ = encode_url(extra_index_url)
    print(f"Install llama_cpp_python_cuda from {extra_index_url}")

    setup_spec.extras["llama_cpp"].append(f"llama_cpp_python_cuda @ {extra_index_url}")


def core_requires():
    """
    pip install db-gpt or pip install "db-gpt[core]"
    """
    setup_spec.extras["core"] = [
        "aiohttp==3.8.4",
        "chardet==5.1.0",
        "importlib-resources==5.12.0",
        "psutil==5.9.4",
        "python-dotenv==1.0.0",
        "colorama==0.4.6",
        "prettytable",
        "cachetools",
    ]

    setup_spec.extras["framework"] = [
        "coloredlogs",
        "httpx",
        "sqlparse==0.4.4",
        "seaborn",
        # https://github.com/eosphoros-ai/DB-GPT/issues/551
        "pandas==2.0.3",
        "auto-gpt-plugin-template",
        "gTTS==2.3.1",
        "langchain>=0.0.286",
        # change from fixed version 2.0.22 to variable version, because other dependencies are >=1.4, such as pydoris is <2
        "SQLAlchemy>=1.4,<3",
        "fastapi==0.98.0",
        "pymysql",
        "duckdb==0.8.1",
        "duckdb-engine",
        "jsonschema",
        # TODO move transformers to default
        # "transformers>=4.31.0",
        "transformers>=4.34.0",
        "alembic==1.12.0",
        # for excel
        "openpyxl==3.1.2",
        "chardet==5.1.0",
        "xlrd==2.0.1",
        # for cache, TODO pympler has not been updated for a long time and needs to find a new toolkit.
        "pympler",
        "aiofiles",
        # for cache
        "msgpack",
        # for agent
        "GitPython",
    ]
    if BUILD_FROM_SOURCE:
        setup_spec.extras["framework"].append(
            f"fschat @ {BUILD_FROM_SOURCE_URL_FAST_CHAT}"
        )
    else:
        setup_spec.extras["framework"].append("fschat")


def knowledge_requires():
    """
    pip install "db-gpt[knowledge]"
    """
    setup_spec.extras["knowledge"] = [
        "spacy==3.5.3",
        "chromadb==0.4.10",
        "markdown",
        "bs4",
        "python-pptx",
        "python-docx",
        "pypdf",
        "python-multipart",
        "sentence-transformers",
    ]


def llama_cpp_requires():
    """
    pip install "db-gpt[llama_cpp]"
    """
    setup_spec.extras["llama_cpp"] = ["llama-cpp-python"]
    llama_cpp_python_cuda_requires()


def _build_autoawq_requires() -> Optional[str]:
    os_type, _ = get_cpu_avx_support()
    if os_type == OSType.DARWIN:
        return None
    auto_gptq_version = get_latest_version(
        "auto-gptq", "https://huggingface.github.io/autogptq-index/whl/cu118/", "0.5.1"
    )
    # eg. 0.5.1+cu118
    auto_gptq_version = auto_gptq_version.split("+")[0]

    def pkg_file_func(pkg_name, pkg_version, cuda_version, py_version, os_type):
        pkg_name = pkg_name.replace("-", "_")
        if os_type == OSType.DARWIN:
            return None
        os_pkg_name = (
            "manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
            if os_type == OSType.LINUX
            else "win_amd64.whl"
        )
        return f"{pkg_name}-{pkg_version}+{cuda_version}-{py_version}-{py_version}-{os_pkg_name}"

    auto_gptq_url = _build_wheels(
        "auto-gptq",
        auto_gptq_version,
        base_url_func=lambda v, x, y: f"https://huggingface.github.io/autogptq-index/whl/{x}/auto-gptq",
        pkg_file_func=pkg_file_func,
        supported_cuda_versions=["11.8"],
    )
    if auto_gptq_url:
        print(f"Install auto-gptq from {auto_gptq_url}")
        return f"auto-gptq @ {auto_gptq_url}"
    else:
        "auto-gptq"


def quantization_requires():
    pkgs = []
    os_type, _ = get_cpu_avx_support()
    if os_type != OSType.WINDOWS:
        pkgs = ["bitsandbytes"]
    else:
        latest_version = get_latest_version(
            "bitsandbytes",
            "https://jllllll.github.io/bitsandbytes-windows-webui",
            "0.41.1",
        )
        extra_index_url = f"https://github.com/jllllll/bitsandbytes-windows-webui/releases/download/wheels/bitsandbytes-{latest_version}-py3-none-win_amd64.whl"
        local_pkg = cache_package(
            extra_index_url, "bitsandbytes", os_type == OSType.WINDOWS
        )
        pkgs = [f"bitsandbytes @ {local_pkg}"]
        print(pkgs)
    # For chatglm2-6b-int4
    pkgs += ["cpm_kernels"]

    if os_type != OSType.DARWIN:
        # Since transformers 4.35.0, the GPT-Q/AWQ model can be loaded using AutoModelForCausalLM.
        # autoawq requirements:
        # 1. Compute Capability 7.5 (sm75). Turing and later architectures are supported.
        # 2. CUDA Toolkit 11.8 and later.
        autoawq_url = _build_wheels(
            "autoawq",
            "0.1.7",
            base_url_func=lambda v, x, y: f"https://github.com/casper-hansen/AutoAWQ/releases/download/v{v}",
            supported_cuda_versions=["11.8"],
        )
        if autoawq_url:
            print(f"Install autoawq from {autoawq_url}")
            pkgs.append(f"autoawq @ {autoawq_url}")
        else:
            pkgs.append("autoawq")

        auto_gptq_pkg = _build_autoawq_requires()
        if auto_gptq_pkg:
            pkgs.append(auto_gptq_pkg)
            pkgs.append("optimum")

    setup_spec.extras["quantization"] = pkgs


def all_vector_store_requires():
    """
    pip install "db-gpt[vstore]"
    """
    setup_spec.extras["vstore"] = [
        "grpcio==1.47.5",  # maybe delete it
        "pymilvus==2.2.1",
        "weaviate-client",
    ]


def all_datasource_requires():
    """
    pip install "db-gpt[datasource]"
    """

    setup_spec.extras["datasource"] = [
        "pymssql",
        "pymysql",
        "pyspark",
        "psycopg2",
        # for doris
        "pydoris>=1.0.2,<2.0.0",
    ]


def openai_requires():
    """
    pip install "db-gpt[openai]"
    """
    setup_spec.extras["openai"] = ["tiktoken"]
    if BUILD_VERSION_OPENAI:
        # Read openai sdk version from env
        setup_spec.extras["openai"].append(f"openai=={BUILD_VERSION_OPENAI}")
    else:
        setup_spec.extras["openai"].append("openai")

    setup_spec.extras["openai"] += setup_spec.extras["framework"]
    setup_spec.extras["openai"] += setup_spec.extras["knowledge"]


def gpt4all_requires():
    """
    pip install "db-gpt[gpt4all]"
    """
    setup_spec.extras["gpt4all"] = ["gpt4all"]


def vllm_requires():
    """
    pip install "db-gpt[vllm]"
    """
    setup_spec.extras["vllm"] = ["vllm"]


def cache_requires():
    """
    pip install "db-gpt[cache]"
    """
    setup_spec.extras["cache"] = ["rocksdict"]


def default_requires():
    """
    pip install "db-gpt[default]"
    """
    setup_spec.extras["default"] = [
        # "tokenizers==0.13.3",
        "tokenizers>=0.14",
        "accelerate>=0.20.3",
        "protobuf==3.20.3",
        "zhipuai",
        "dashscope",
        "chardet",
    ]
    setup_spec.extras["default"] += setup_spec.extras["framework"]
    setup_spec.extras["default"] += setup_spec.extras["knowledge"]
    setup_spec.extras["default"] += setup_spec.extras["torch"]
    setup_spec.extras["default"] += setup_spec.extras["quantization"]
    setup_spec.extras["default"] += setup_spec.extras["cache"]


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
torch_requires()
knowledge_requires()
llama_cpp_requires()
quantization_requires()

all_vector_store_requires()
all_datasource_requires()
openai_requires()
gpt4all_requires()
vllm_requires()
cache_requires()

# must be last
default_requires()
all_requires()
init_install_requires()

setuptools.setup(
    name="db-gpt",
    packages=find_packages(exclude=("tests", "*.tests", "*.tests.*", "examples")),
    version="0.4.4",
    author="csunny",
    author_email="cfqcsunny@gmail.com",
    description="DB-GPT is an experimental open-source project that uses localized GPT large models to interact with your data and environment."
    " With this solution, you can be assured that there is no risk of data leakage, and your data is 100% private and secure.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=setup_spec.install_requires,
    url="https://github.com/eosphoros-ai/DB-GPT",
    license="https://opensource.org/license/mit/",
    python_requires=">=3.10",
    extras_require=setup_spec.extras,
    entry_points={
        "console_scripts": [
            "dbgpt=dbgpt.cli.cli_scripts:main",
        ],
    },
)
