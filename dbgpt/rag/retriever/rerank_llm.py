# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/6 上午10:38
'''
import json
from pprint import pprint
from typing import List, Optional, Dict
from dbgpt.core import LLMClient, ModelMessage, ModelRequest, ModelMessageRoleType

RERANK_PROMPT_TEMPLATE_EN = """
There are some tables info
{restriever_info}

query : {original_query}

Return format: {"Relate_tables": "Tables needed for the query", 'rewrite_query': "Reconstructed issue content"}

Ensure the return is correct JSON and can be parsed by the Python json.loads method.
"""

RERANK_PROMPT_TEMPLATE_ZH = """
现在有以下表信息

{restriever_info}

问题：{original_query}

返回格式：{response}

确保返回正确的json并且可以被Python json.loads方法解析.
"""
RESPONSE_FORMAT_SIMPLE_ZH = {
    "Relate_tables": "请你一步一步思考并且得出与问题相关的所有表名的列表，不要出现字段名。",
}
RESPONSE_FORMAT_SIMPLE_EN = {
    "Relate_tables": "Tables name: think it step by step needed for the query",
}


class QueryRerank:
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
            RERANK_PROMPT_TEMPLATE_EN
            if language == "en"
            else RERANK_PROMPT_TEMPLATE_ZH
        )

    async def rerank(self, origin_query: str, restriever_info: str) -> List[str]:
        """query rewrite
        Args:
            origin_query: str original query
            restriever_info:  restriever_info
        Returns:
            queries: List[str]
        """
        from dbgpt.util.chat_util import run_async_tasks
        temperature = 0
        prompt = self._prompt_template.format(
            original_query=origin_query,
            restriever_info=restriever_info,
            response=json.dumps(
                RESPONSE_FORMAT_SIMPLE_EN if self._language == "en" else RESPONSE_FORMAT_SIMPLE_ZH,
                ensure_ascii=False,
                indent=4))

        messages = [ModelMessage(role=ModelMessageRoleType.SYSTEM, content=prompt)]
        request = ModelRequest(model=self._model_name, messages=messages, temperature=temperature)
        pprint(request)
        tasks = [self._llm_client.generate(request)]
        queries = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        queries = [model_out.text for model_out in queries]
        queries = list(
            filter(
                lambda content: "LLMServer Generate Error" not in content,
                queries,
            )
        )
        return self._parse_llm_output(output=queries[0])

    def correct(self) -> List[str]:
        pass

    def _parse_llm_output(self, output: str) -> Dict:
        """parse llm output
        Args:
            output: str
        Returns:
            output: Dict
        """
        try:
            output = output.strip()
            output = output.strip('```')
            output = output.strip('json')

            results = json.loads(output)
            if not isinstance(results['Relate_tables'], list):
                if '(' in results['Relate_tables']:
                    results['Relate_tables'] = results['Relate_tables'].split('(')[0].strip()
                else:
                    results['Relate_tables'] = results['Relate_tables'].split(',')
                    results['Relate_tables'] = [r.strip() for r in results['Relate_tables']]
            else:
                results['Relate_tables'] = [r.strip() for r in results['Relate_tables']]
        except Exception as e:
            print(f"parse query rewrite prompt_response error: {e}")
            return {}
        return results


if __name__ == '__main__':
    qw = QueryRerank()
