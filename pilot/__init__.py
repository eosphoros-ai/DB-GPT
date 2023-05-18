from pilot.source_embedding import (SourceEmbedding, register)

import os
import sys

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

__all__ = [
    "SourceEmbedding",
    "register"
]
