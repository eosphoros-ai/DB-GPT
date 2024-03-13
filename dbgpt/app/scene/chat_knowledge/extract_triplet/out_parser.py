import logging
import re
from typing import List, Tuple

from dbgpt.core.interface.output_parser import BaseOutputParser

logger = logging.getLogger(__name__)


class ExtractTripleParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_prompt_response(
        self, response, max_length: int = 128
    ) -> List[Tuple[str, str, str]]:
        # clean_str = super().parse_prompt_response(response)
        print("clean prompt response:", response)

        if response.startswith("Triplets:"):
            response = response[len("Triplets:") :]
            pattern = r"\([^()]+\)"
            response = re.findall(pattern, response)
        # response = response.strip().split("\n")
        print("parse prompt response:", response)
        results = []
        for text in response:
            if not text or text[0] != "(" or text[-1] != ")":
                # skip empty lines and non-triplets
                continue
            tokens = text[1:-1].split(",")
            if len(tokens) != 3:
                continue

            if any(len(s.encode("utf-8")) > max_length for s in tokens):
                # We count byte-length instead of len() for UTF-8 chars,
                # will skip if any of the tokens are too long.
                # This is normally due to a poorly formatted triplet
                # extraction, in more serious KG building cases
                # we'll need NLP models to better extract triplets.
                continue

            subject, predicate, obj = map(str.strip, tokens)
            if not subject or not predicate or not obj:
                # skip partial triplets
                continue
            results.append((subject.lower(), predicate.lower(), obj.lower()))
        return results

    def parse_view_response(self, speak, data) -> str:
        ### tool out data to table view
        return data
