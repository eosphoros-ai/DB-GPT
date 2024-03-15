import json
from datetime import datetime
from typing import Dict
from dbgpt._private.config import Config
from dbgpt.agent.plugin.commands.command_manage import ApiCall
from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.rag.retriever.rerank_llm import QueryRerank
from dbgpt.rag.retriever.rerank import RRFRanker
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import root_tracer, trace
import re

CFG = Config()


async def rerank_llm(query, restriever_info, language='zh'):
    import os
    api_key = '3d4c01e9d3264c8aa8e6469411beadff'
    api_base = 'https://gpt001-6.openai.azure.com/'
    api_type = 'azure'
    api_version = '2024-02-15-preview'
    os.environ["OPENAI_API_BASE"] = api_base
    os.environ["OPENAI_API_VERSION"] = api_version
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_API_TYPE"] = api_type
    llm_client = OpenAILLMClient(temperature=0)
    reinforce = QueryRerank(
        llm_client=llm_client,
        model_name="gpt-4-0314",
        language=language
    )
    return await reinforce.rerank(origin_query=query, restriever_info=restriever_info)


class ChatWithDbAutoExecute(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbExecute.value()

    """Number of results to return from the query"""

    def __init__(self, chat_param: Dict):
        """Chat Data Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) dbname
        """
        chat_mode = ChatScene.ChatWithDbExecute
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = chat_mode
        """ """
        super().__init__(
            chat_param=chat_param,
        )
        if not self.db_name:
            raise ValueError(
                f"{ChatScene.ChatWithDbExecute.value} mode should chose db!"
            )
        with root_tracer.start_span(
                "ChatWithDbAutoExecute.get_connect", metadata={"db_name": self.db_name}
        ):
            self.database = CFG.LOCAL_DB_MANAGE.get_connect(self.db_name)

        self.top_k: int = 50
        self.api_call = ApiCall(display_registry=CFG.command_dispaly)

    @trace()
    async def generate_input_values(self) -> Dict:
        """
        generate input values
        """
        try:
            from dbgpt.rag.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")

        client = DBSummaryClient(system_app=CFG.SYSTEM_APP)

        with open('/datas/liab/DB-GPT/tests/atl_data/type3/qa_samples.json', 'r') as f:
            contents = json.load(f)
        with root_tracer.start_span("ChatWithDbAutoExecute.get_db_summary"):
            qas_info = await blocking_func_to_async(
                self._executor,
                client.get_db_summary,
                'type3_qasamples',
                self.current_user_input,
                6,
            )

        qa_samples = ''
        qa_tables = []

        for ii, qa in enumerate(qas_info):
            qa_samples += '\t用户输入%s：' % (ii + 1)
            qa_samples += qa + '\n'
            qa_samples += '\tsql%s：' % (ii + 1)
            qa_samples += str(contents.get(qa)) + '\n\n'
            qa_tables.extend(re.findall('(a_sap\w*)', contents.get(qa)))

            print('qa_tables::', re.findall('(a_sap\w*)', contents.get(qa)))
        # BM25
        with root_tracer.start_span("ChatWithDbAutoExecute.get_db_bm25"):
            bm25_tmep = await blocking_func_to_async(
                self._executor,
                client.get_db_bm25,
                self.db_name,
                self.current_user_input,
                0.001,
            )

        for i in bm25_tmep:
            print('bm25_tmep:::', i.split(',')[0])
        print()

        # embedding similarity
        try:
            with root_tracer.start_span("ChatWithDbAutoExecute.get_db_summary"):
                table_infos = await blocking_func_to_async(
                    self._executor,
                    client.get_db_summary,
                    self.db_name,
                    self.current_user_input,
                    5,
                )

        except Exception as e:
            import traceback
            print(traceback.print_exc())
            print("db summary find error!1" + str(e))

        for i in table_infos:
            print('table_infos:::', i.split(',')[0])
        print()

        all_table_infos = await blocking_func_to_async(
            self._executor, self.database.table_simple_info
        )
        print('all_table_infos---------------', all_table_infos, 'all_table_infos')

        table_map = {}
        for i in all_table_infos:
            if i[0]:
                table_map[i[0].strip().strip('Table').strip(':').split(',')[0].strip()] = i[0] + i[1]
                # table_map[i.strip().strip('Table:').split('(')[0].strip()] = 'Table:' + i + ',columns:(' + i[1] + ')'
            else:
                pass

        # Ensemble RRF ranker
        rrf_ranker = RRFRanker(topk=4, weights=[0.3, 0.3, 0.4])
        rrf_ranker_scores = rrf_ranker.rank(
            [table_infos, bm25_tmep, [table_map[table_name] for table_name in qa_tables if table_name in table_map.keys()]])
        print('LLM reranker ')
        print('table_map::', table_map)
        print()
        rerank_result = await rerank_llm(self.current_user_input, '\n'.join([rrf.content for rrf in rrf_ranker_scores]))

        print('rerank_result::', rerank_result)
        tables_rerank_info = []
        if table_map:
            for table in rerank_result['Relate_tables']:
                tables_rerank_info.append(table_map[table.strip('`')])

        table_infos = '\n'.join(tables_rerank_info)

        with root_tracer.start_span("ChatWithDbAutoExecute.get_db_bm25"):
            bm25_general_tmep = await blocking_func_to_async(
                self._executor,
                client.get_db_bm25,
                'type2_general',
                self.current_user_input,
                0.3,
            )

        with root_tracer.start_span("ChatWithDbAutoExecute.get_db_bm25"):
            bm25_department_temp = await blocking_func_to_async(
                self._executor,
                client.get_db_bm25,
                'new_department',
                self.current_user_input,
                0.7,
            )
        if len(bm25_department_temp) > 0:
            bm25_department_text = '如下用Markdown表格结构来说明部门机构的关系。\n'
            bm25_department_text += '\n'.join(bm25_department_temp)
        else:
            bm25_department_text = ''

        extend_infos = '\n'.join(bm25_general_tmep) + bm25_department_text
        input_values = {
            "db_name": self.db_name,
            "user_input": self.current_user_input,
            "top_k": str(self.top_k),
            "dialect": self.database.dialect,
            "table_info": table_infos,
            "extend_info": extend_infos,
            "display_type": self._generate_numbered_list(),
            "qa_samples": qa_samples,
            "current_date": datetime.now().strftime("%Y-%m-%d"),
        }
        return input_values

    def stream_plugin_call(self, text):
        text = text.replace("\n", " ")
        print(f"stream_plugin_call:{text}")
        return self.api_call.display_sql_llmvis(text, self.database.run_to_df)

    def do_action(self, prompt_response):
        print(f"do_action2:{prompt_response}")
        return self.database.run_to_df
