import re
from typing import Optional, Tuple


def parse_conv_id(conv_id: str) -> Tuple[str, Optional[int]]:
    pattern = r"([\w-]+)_(\d+)"
    match = re.match(pattern, conv_id)
    if match:
        # TODO: conv_id passed from serve module will be like "real_conv_id_1" now,
        #  so we need to extract
        # the real conv_id
        real_conv_id = match.group(1)
        # Extract the number part
        number_part = match.group(2)
        return real_conv_id, number_part
    else:
        return conv_id, None
