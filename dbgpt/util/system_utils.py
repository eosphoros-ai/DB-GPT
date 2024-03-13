import os
import platform
import re
import subprocess
from dataclasses import asdict, dataclass
from enum import Enum
from functools import cache
from typing import Dict, Tuple


@dataclass
class SystemInfo:
    platform: str
    distribution: str
    python_version: str
    cpu: str
    cpu_avx: str
    memory: str
    torch_version: str
    device: str
    device_version: str
    device_count: int
    device_other: str

    def to_dict(self) -> Dict:
        return asdict(self)


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


class OSType(str, Enum):
    WINDOWS = "win"
    LINUX = "linux"
    DARWIN = "darwin"
    OTHER = "other"


def get_cpu_avx_support() -> Tuple[OSType, AVXType, str]:
    system = platform.system()
    os_type = OSType.OTHER
    cpu_avx = AVXType.BASIC
    env_cpu_avx = AVXType.of_type(os.getenv("DBGPT_LLAMA_CPP_AVX"))
    distribution = "Unknown Distribution"
    if "windows" in system.lower():
        os_type = OSType.WINDOWS
        output = "avx2"
        distribution = "Windows " + platform.release()
        print("Current platform is windows, use avx2 as default cpu architecture")
    elif system == "Linux":
        os_type = OSType.LINUX
        result = subprocess.run(
            ["lscpu"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = result.stdout.decode()
        distribution = get_linux_distribution()
    elif system == "Darwin":
        os_type = OSType.DARWIN
        result = subprocess.run(
            ["sysctl", "-a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        distribution = "Mac OS " + platform.mac_ver()[0]
        output = result.stdout.decode()
    else:
        os_type = OSType.OTHER
        print("Unsupported OS to get cpu avx, use default")
        return os_type, env_cpu_avx if env_cpu_avx else cpu_avx, distribution

    if "avx512" in output.lower():
        cpu_avx = AVXType.AVX512
    elif "avx2" in output.lower():
        cpu_avx = AVXType.AVX2
    elif "avx " in output.lower():
        # cpu_avx =  AVXType.AVX
        pass
    return os_type, env_cpu_avx if env_cpu_avx else cpu_avx, distribution


def get_device() -> str:
    try:
        import torch

        return (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
    except ModuleNotFoundError:
        return "cpu"


def get_device_info() -> Tuple[str, str, str, int, str]:
    torch_version, device, device_version, device_count, device_other = (
        None,
        "cpu",
        None,
        0,
        "",
    )
    try:
        import torch

        torch_version = torch.__version__
        if torch.cuda.is_available():
            device = "cuda"
            device_version = torch.version.cuda
            device_count = torch.cuda.device_count()
        elif torch.backends.mps.is_available():
            device = "mps"
    except ModuleNotFoundError:
        pass

    if not device_version:
        device_version = (
            get_cuda_version_from_nvcc() or get_cuda_version_from_nvidia_smi()
        )
    if device == "cuda":
        try:
            output = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,driver_version,memory.total,memory.free,memory.used",
                    "--format=csv",
                ]
            )
            device_other = output.decode("utf-8")
        except:
            pass
    return torch_version, device, device_version, device_count, device_other


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


def get_linux_distribution():
    """Get distribution of Linux"""
    if os.path.isfile("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            info = {}
            for line in f:
                key, _, value = line.partition("=")
                info[key] = value.strip().strip('"')
            return f"{info.get('NAME', 'Unknown')} {info.get('VERSION_ID', '')}".strip()
    return "Unknown Linux Distribution"


def get_cpu_info():
    # Getting platform
    os_type, avx_type, distribution = get_cpu_avx_support()

    # Getting CPU information
    cpu_info = "Unknown CPU"
    if os_type == OSType.LINUX:
        try:
            output = subprocess.check_output(["lscpu"]).decode("utf-8")
            match = re.search(r".*Model name:\s*(.+)", output)
            if match:
                cpu_info = match.group(1).strip()
            match = re.search(f".*型号名称：\s*(.+)", output)
            if match:
                cpu_info = match.group(1).strip()
        except:
            pass
    elif os_type == OSType.DARWIN:
        try:
            output = subprocess.check_output(
                ["sysctl", "machdep.cpu.brand_string"]
            ).decode("utf-8")
            match = re.search(r"machdep.cpu.brand_string:\s*(.+)", output)
            if match:
                cpu_info = match.group(1).strip()
        except:
            pass
    elif os_type == OSType.WINDOWS:
        try:
            output = subprocess.check_output("wmic cpu get Name", shell=True).decode(
                "utf-8"
            )
            lines = output.splitlines()
            cpu_info = lines[2].split(":")[-1].strip()
        except:
            pass

    return os_type, avx_type, cpu_info, distribution


def get_memory_info(os_type: OSType) -> str:
    memory = "Unknown Memory"
    try:
        import psutil

        memory = f"{psutil.virtual_memory().total // (1024 ** 3)} GB"
    except ImportError:
        pass
    if os_type == OSType.LINUX:
        try:
            with open("/proc/meminfo", "r") as f:
                mem_info = f.readlines()
            for line in mem_info:
                if "MemTotal" in line:
                    memory = line.split(":")[1].strip()
                    break
        except:
            pass
    return memory


@cache
def get_system_info() -> SystemInfo:
    """Get System information"""

    os_type, avx_type, cpu_info, distribution = get_cpu_info()

    # Getting Python version
    python_version = platform.python_version()

    memory = get_memory_info(os_type)

    (
        torch_version,
        device,
        device_version,
        device_count,
        device_other,
    ) = get_device_info()

    return SystemInfo(
        platform=os_type._value_,
        distribution=distribution,
        python_version=python_version,
        cpu=cpu_info,
        cpu_avx=avx_type._value_,
        memory=memory,
        torch_version=torch_version,
        device=device,
        device_version=device_version,
        device_count=device_count,
        device_other=device_other,
    )
