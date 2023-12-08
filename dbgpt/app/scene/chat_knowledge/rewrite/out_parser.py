import logging

from dbgpt.core.interface.output_parser import BaseOutputParser

logger = logging.getLogger(__name__)


class QueryRewriteParser(BaseOutputParser):
    def __init__(self, is_stream_out: bool, **kwargs):
        super().__init__(is_stream_out=is_stream_out, **kwargs)

    def parse_prompt_response(self, response, max_length: int = 128):
        lowercase = True
        try:
            results = []
            response = response.strip()

            if response.startswith("queries:"):
                response = response[len("queries:") :]

            queries = response.split(",")
            if len(queries) == 1:
                queries = response.split("，")
            if len(queries) == 1:
                queries = response.split("?")
            if len(queries) == 1:
                queries = response.split("？")
            for k in queries:
                rk = k
                if lowercase:
                    rk = rk.lower()
                s = rk.strip()
                if s == "":
                    continue
                results.append(s)
        except Exception as e:
            logger.error(f"parse query rewrite prompt_response error: {e}")
            return []
        return results

    def parse_view_response(self, speak, data) -> str:
        return data
