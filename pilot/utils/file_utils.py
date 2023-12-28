import os
import time


def wait_for_file_exist(path, timeout=3000):
    """
    Checks if the file exists, if not, waits until the file appears or times out.

    Params:
    path -- absolute path to file
    timeout -- Timeout in milliseconds (default 3000 milliseconds)

    Return:
    True -- if file existed
    False -- If the wait times out and the file still doesn't exist
    """
    start_time = time.time()
    timeout_seconds = timeout / 1000.0
    while True:
        if os.path.exists(path):
            return True
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout_seconds:
            return False
        time.sleep(0.1)
