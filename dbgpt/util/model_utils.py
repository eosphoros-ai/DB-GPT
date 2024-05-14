import logging
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


def _clear_model_cache(device="cuda"):
    try:
        # clear torch cache
        import torch

        _clear_torch_cache(device)
    except ImportError:
        logger.warn("Torch not installed, skip clear torch cache")
    # TODO clear other cache


def _clear_torch_cache(device="cuda"):
    import gc

    import torch

    gc.collect()
    if device != "cpu":
        if torch.has_mps:
            try:
                from torch.mps import empty_cache

                empty_cache()
            except Exception as e:
                logger.warn(f"Clear mps torch cache error, {str(e)}")
        elif torch.has_cuda:
            device_count = torch.cuda.device_count()
            for device_id in range(device_count):
                cuda_device = f"cuda:{device_id}"
                logger.info(f"Clear torch cache of device: {cuda_device}")
                with torch.cuda.device(cuda_device):
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
        else:
            logger.info("No cuda or mps, not support clear torch cache yet")


@dataclass
class GPUInfo:
    total_memory_gb: float
    allocated_memory_gb: float
    cached_memory_gb: float
    available_memory_gb: float


def _get_current_cuda_memory() -> List[GPUInfo]:
    try:
        import torch
    except ImportError:
        logger.warn("Torch not installed")
        return []
    if torch.cuda.is_available():
        num_gpus = torch.cuda.device_count()
        gpu_infos = []
        for gpu_id in range(num_gpus):
            with torch.cuda.device(gpu_id):
                device = torch.cuda.current_device()
                gpu_properties = torch.cuda.get_device_properties(device)
                total_memory = round(gpu_properties.total_memory / (1.0 * 1024**3), 2)
                allocated_memory = round(
                    torch.cuda.memory_allocated() / (1.0 * 1024**3), 2
                )
                cached_memory = round(
                    torch.cuda.memory_reserved() / (1.0 * 1024**3), 2
                )
                available_memory = total_memory - allocated_memory
                gpu_infos.append(
                    GPUInfo(
                        total_memory_gb=total_memory,
                        allocated_memory_gb=allocated_memory,
                        cached_memory_gb=cached_memory,
                        available_memory_gb=available_memory,
                    )
                )
        return gpu_infos
    else:
        logger.warn("CUDA is not available.")
        return []
