import logging


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
                logging.warn(f"Clear mps torch cache error, {str(e)}")
        elif torch.has_cuda:
            device_count = torch.cuda.device_count()
            for device_id in range(device_count):
                cuda_device = f"cuda:{device_id}"
                logging.info(f"Clear torch cache of device: {cuda_device}")
                with torch.cuda.device(cuda_device):
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
        else:
            logging.info("No cuda or mps, not support clear torch cache yet")
