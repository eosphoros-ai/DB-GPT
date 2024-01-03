from typing import List, Optional
from dbgpt.core import LLMClient, ModelMessage, ModelRequest, ModelMessageRoleType

REWRITE_PROMPT_TEMPLATE_EN = """
Generate {nums} search queries related to: {original_query}, Provide following comma-separated format: 'queries: <queries>'\n":
    "original query:: {original_query}\n"
    "queries:\n"
"""

REWRITE_PROMPT_TEMPLATE_ZH = """请根据原问题优化生成{nums}个相关的搜索查询，这些查询应与原始查询相似并且是人们可能会提出的可回答的搜索问题。请勿使用任何示例中提到的内容，确保所有生成的查询均独立于示例，仅基于提供的原始查询。请按照以下逗号分隔的格式提供: 'queries：<queries>'：
"original_query：{original_query}\n"
"queries：\n"
"""


class QueryRewrite:
    """
    query reinforce, include query rewrite, query correct
    """

    def __init__(
        self,
        model_name: str = None,
        llm_client: Optional[LLMClient] = None,
        language: Optional[str] = "en",
    ) -> None:
        """query rewrite
        Args:
            - query: (str), user query
            - model_name: (str), llm model name
            - llm_client: (Optional[LLMClient])
        """
        self._model_name = model_name
        self._llm_client = llm_client
        self._language = language
        self._prompt_template = (
            REWRITE_PROMPT_TEMPLATE_EN
            if language == "en"
            else REWRITE_PROMPT_TEMPLATE_ZH
        )

    async def rewrite(self, origin_query: str, nums: Optional[int] = 1) -> List[str]:
        """query rewrite
        Args:
            origin_query: str original query
            nums: Optional[int] rewrite nums
        Returns:
            queries: List[str]
        """
        from dbgpt.util.chat_util import run_async_tasks

        prompt = self._prompt_template.format(original_query=origin_query, nums=nums)
        messages = [ModelMessage(role=ModelMessageRoleType.SYSTEM, content=prompt)]
        request = ModelRequest(model=self._model_name, messages=messages)
        tasks = [self._llm_client.generate(request)]
        queries = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        queries = [model_out.text for model_out in queries]
        queries = list(
            filter(
                lambda content: "LLMServer Generate Error" not in content,
                queries,
            )
        )
        print("rewrite queries:", queries)
        return self._parse_llm_output(output=queries[0])

    def correct(self) -> List[str]:
        pass

    def _parse_llm_output(self, output: str) -> List[str]:
        """parse llm output
        Args:
            output: str
        Returns:
            output: List[str]
        """
        lowercase = True
        try:
            results = []
            response = output.strip()

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
            print(f"parse query rewrite prompt_response error: {e}")
            return []
        return results
