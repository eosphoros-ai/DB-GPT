"""Host tool resource module."""

from ...resource.tool.base import tool


@tool(description="Get current host CPU status.")
def get_current_host_cpu_status() -> str:
    """Get current host CPU status."""
    import platform

    import psutil

    cpu_architecture = platform.machine()
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_usage = psutil.cpu_percent(interval=1)
    return (
        f"CPU Architecture: {cpu_architecture}\n"
        f"Physical CPU Cores: {cpu_count_physical}\n"
        f"Logical CPU Cores: {cpu_count_logical}\n"
        f"CPU Usage: {cpu_usage}%"
    )


@tool(description="Get current host memory status.")
def get_current_host_memory_status() -> str:
    """Get current host memory status."""
    import psutil

    memory = psutil.virtual_memory()
    return (
        f"Total:  {memory.total / (1024**3):.2f} GB\n"
        f"Available: {memory.available / (1024**3):.2f} GB\n"
        f"Used:  {memory.used / (1024**3):.2f} GB\n"
        f"Percent: {memory.percent}%"
    )


@tool(description="Get current host system load.")
def get_current_host_system_load() -> str:
    """Get current host system load."""
    import os

    load1, load5, load15 = os.getloadavg()
    return f"System load average: {load1:.2f}, {load5:.2f}, {load15:.2f}"
