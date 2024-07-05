"""Financial Report Assembler."""
import glob
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional

import pandas as pd
from pandas import DataFrame
from tqdm import tqdm

from dbgpt.core import Chunk, Document, Embeddings
from dbgpt.rag.knowledge.fin_report import FinReportKnowledge

from ...component import logger
from ...datasource.db_conn_info import DBConfig
from ...datasource.manages import ConnectorManager
from ...datasource.rdbms.base import RDBMSConnector
from ...datasource.rdbms.conn_sqlite import SQLiteConnector
from ...util.executor_utils import blocking_func_to_async
from ...util.tracer import root_tracer
from ..assembler.base import BaseAssembler
from ..chunk_manager import ChunkParameters
from ..extractor.financial_table import FinTableExtractor, FinTableProcessor
from ..index.base import IndexStoreBase
from ..retriever import BaseRetriever, RetrieverStrategy
from ..retriever.embedding import EmbeddingRetriever


class FinReportAssembler(BaseAssembler):
    """Embedding Assembler.

    Example:
    .. code-block:: python

        from dbgpt.rag.assembler import EmbeddingAssembler

        pdf_path = "path/to/document.pdf"
        knowledge = KnowledgeFactory.from_file_path(pdf_path)
        assembler = EmbeddingAssembler.load_from_knowledge(
            knowledge=knowledge,
            embedding_model="text2vec",
        )
    """

    def __init__(
        self,
        knowledge: FinReportKnowledge,
        index_store: IndexStoreBase,
        conn_database: Optional[RDBMSConnector] = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        retrieve_strategy: Optional[RetrieverStrategy] = RetrieverStrategy.HYBRID,
        tmp_dir_path: Optional[str] = None,
        verbose: Optional[bool] = True,
        connector_manager: Optional[ConnectorManager] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.

        Args:
            knowledge: (FinReportKnowledge) FinReportKnowledge datasource.
            index_store: (IndexStoreBase) IndexStoreBase to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            keyword_store: (Optional[IndexStoreBase]) IndexStoreBase to use.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
        """
        if knowledge is None:
            raise ValueError("knowledge datasource must be provided.")
        self._index_store = index_store
        self._conn_database = conn_database or SQLiteConnector.from_file_path(
            (tmp_dir_path or "./tmp") + "/fin_report.db"
        )
        self._retrieve_strategy = retrieve_strategy
        self._file_path = knowledge.file_path
        self._tmp_dir_path = (tmp_dir_path or "./tmp") + f"/{uuid.uuid4()}"
        self._tmp_txt_path = os.path.join(
            self._tmp_dir_path + "/txt",
            os.path.basename(knowledge.file_path).replace(".pdf", ".txt"),
        )
        self._tmp_excel_path = os.path.expanduser(self._tmp_dir_path + "/output/excel")
        self._verbose = verbose
        self._final_table_df = None
        if not connector_manager:
            raise ValueError("connector_manager must be provided.")
        self._connector_manager = connector_manager
        self._executor = ThreadPoolExecutor()

        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            **kwargs,
        )

    @classmethod
    def load_from_knowledge(
        cls,
        knowledge: FinReportKnowledge,
        index_store: IndexStoreBase,
        conn_database: Optional[RDBMSConnector] = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        retrieve_strategy: Optional[RetrieverStrategy] = RetrieverStrategy.EMBEDDING,
        tmp_dir_path: Optional[str] = None,
        verbose: Optional[bool] = True,
        connector_manager: Optional[ConnectorManager] = None,
    ) -> "FinReportAssembler":
        """Load document embedding into vector store from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            index_store: (IndexStoreBase) IndexStoreBase to use.
            conn_database: (Optional[RDBMSConnector]) RDBMSConnector to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
            retrieve_strategy: (Optional[RetrieverStrategy]) Retriever strategy.
            tmp_dir_path: (Optional[str]) Temporary directory path.
            verbose: (Optional[bool]) Verbose mode.
            connector_manager: (ConnectorManager) ConnectorManager to use.
        Returns:
             EmbeddingAssembler
        """
        return cls(
            knowledge=knowledge,
            index_store=index_store,
            conn_database=conn_database,
            chunk_parameters=chunk_parameters,
            embedding_model=embedding_model,
            embeddings=embeddings,
            retrieve_strategy=retrieve_strategy,
            tmp_dir_path=tmp_dir_path,
            verbose=verbose,
            connector_manager=connector_manager,
        )

    @classmethod
    async def aload_from_knowledge(
        cls,
        knowledge: FinReportKnowledge,
        index_store: IndexStoreBase,
        conn_database: Optional[RDBMSConnector] = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        executor: Optional[ThreadPoolExecutor] = None,
        retrieve_strategy: Optional[RetrieverStrategy] = RetrieverStrategy.HYBRID,
        tmp_dir_path: Optional[str] = None,
        verbose: Optional[bool] = True,
        connector_manager: Optional[ConnectorManager] = None,
    ) -> "FinReportAssembler":
        """Load document embedding into vector store from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            index_store: (IndexStoreBase) IndexStoreBase to use.
            conn_database: (Optional[RDBMSConnector]) RDBMSConnector to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            executor: (Optional[ThreadPoolExecutor) ThreadPoolExecutor to use.
            retrieve_strategy: (Optional[RetrieverStrategy]) Retriever strategy.
            tmp_dir_path: (Optional[str]) Temporary directory path.
            verbose: (Optional[bool]) Verbose mode.
            connector_manager: (ConnectorManager) ConnectorManager to use.
        """
        executor = executor or ThreadPoolExecutor()
        return await blocking_func_to_async(
            executor,
            cls,
            knowledge,
            index_store,
            conn_database,
            chunk_parameters,
            retrieve_strategy,
            tmp_dir_path,
            verbose,
            connector_manager,
        )

    def load_knowledge(
        self, knowledge: Optional[FinReportKnowledge] = None
    ) -> None:  # type: ignore
        """Load knowledge Pipeline."""
        if not knowledge:
            raise ValueError("knowledge must be provided.")
        with root_tracer.start_span("FinReportAssembler.knowledge.load"):
            knowledge.load()
            self._save_all_text(all_text=knowledge.all_text)
            if self._verbose:
                logger.info(f"fin report pdf -> txt finished,{self._tmp_dir_path}")
            # extract financial report table data
            self._final_table_df = self.table_extract()  # type: ignore
            merged_data = {}  # type: ignore
            for i, item in list(knowledge.all_text.items()):
                page = item.get("page")
                inside = item.get("inside")
                if page in merged_data:
                    merged_data[page] += " " + inside
                else:
                    merged_data[page] = inside
            page_documents = []
            for item in list(merged_data.items()):
                page_documents.append(
                    Document(content=item[1], metadata={"page": item[0]})
                )
        with root_tracer.start_span("FinReportAssembler.chunk_manager.split"):
            self._chunks = self._chunk_manager.split(page_documents)

    def persist(
        self, db_config: DBConfig, conn_database: RDBMSConnector
    ) -> List[str]:  # type: ignore
        """Persist chunks into store.

        Returns:
            List[str]: List of chunk ids.
        """
        # persist chunks into index store
        if self._index_store:
            self._index_store.load_document(self._chunks)
        # persist table data_frame into db
        if conn_database:
            final_report_df = pd.read_excel(
                self._tmp_excel_path + "/table_data_final.xlsx"
            )
            final_report_df.to_sql(
                "fin_report",
                conn_database._engine,
                if_exists="append",
                index=False,
            )
            db_list = [
                item["db_name"] for item in self._connector_manager.get_db_list()
            ]
            # datasource_name = self._tmp_dir_path.rsplit("/", 1)[-1] + "_" + \
            #                   self._conn_database.get_current_db_name()
            if db_config.db_name not in db_list:
                self._connector_manager.add_db(db_config)
        else:
            raise ValueError("fin report db_summary_client initialize failed.")

        return [chunk.chunk_id for chunk in self._chunks]

    async def apersist(  # type: ignore
        self,
        db_config: Optional[DBConfig] = None,
        conn_database: Optional[RDBMSConnector] = None,
    ) -> List[str]:
        """Persist chunks into store.

        Returns:
            List[str]: List of chunk ids.
        """
        # apersist chunks into vector store

        return await blocking_func_to_async(
            self._executor, self.persist, db_config, conn_database
        )

    def table_extract(self) -> DataFrame:
        """Extract knowledge from text."""
        # read txt file
        file_names = glob.glob(self._tmp_dir_path + "/txt/*")
        file_names = sorted(file_names, reverse=True)
        print("now process files: " + str(file_names))

        # process base col
        results = []

        df1 = pd.DataFrame(
            columns=[
                "文件名",
                "日期",
                "公司名称",
                "股票代码",
                "股票简称",
                "年份",
                "类型",
                "代码",
                "简称",
                "电子信箱",
                "注册地址",
                "办公地址",
                "中文名称",
                "中文简称",
                "外文名称",
                "外文名称缩写",
                "公司网址",
                "法定代表人",
                "职工总数",
                "生产人员",
                "销售人员",
                "技术人员",
                "财务人员",
                "行政人员",
                "本科及以上人员",
                "本科人员",
                "硕士及以上人员",
                "硕士人员",
                "博士及以上人员",
                "博士人员",
                "研发人数",
                "全文",
            ]
        )

        for file_name in file_names:
            txt_extracter = FinTableExtractor(file_name)
            results.append(txt_extracter.extract_base_col())

        df1 = pd.DataFrame(results)
        if not os.path.exists(self._tmp_excel_path):
            os.makedirs(self._tmp_excel_path)
        df1.to_excel(self._tmp_excel_path + "table_data_base_info.xlsx", index=False)

        results = []
        list1 = [
            "文件名",
            "日期",
            "公司名称",
            "股票代码",
            "股票简称",
            "年份",
            "类型",
            "合并资产负债表",
            "合并利润表",
            "合并利润表",
            "全文",
        ]
        list2 = [
            "货币资金",
            "结算备付金",
            "拆出资金",
            "交易性金融资产",
            "以公允价值计量且其变动计入当期损益的金融资产",
            "衍生金融资产",
            "应收票据",
            "应收账款",
            "应收款项融资",
            "预付款项",
            "应收保费",
            "应收分保账款",
            "应收分保合同准备金",
            "其他应收款",
            "应收利息",
            "应收股利",
            "买入返售金融资产",
            "存货",
            "合同资产",
            "持有待售资产",
            "一年内到期的非流动资产",
            "其他流动资产",
            "流动资产合计",
            "发放贷款和垫款",
            "债权投资",
            "可供出售金融资产",
            "其他债权投资",
            "持有至到期投资",
            "长期应收款",
            "长期股权投资",
            "其他权益工具投资",
            "其他非流动金融资产",
            "投资性房地产",
            "固定资产",
            "在建工程",
            "生产性生物资产",
            "油气资产",
            "使用权资产",
            "无形资产",
            "开发支出",
            "商誉",
            "长期待摊费用",
            "递延所得税资产",
            "其他非流动资产",
            "非流动资产合计",
            "资产总计",
            "短期借款",
            "向中央银行借款",
            "拆入资金",
            "交易性金融负债",
            "以公允价值计量且其变动计入当期损益的金融负债",
            "衍生金融负债",
            "应付票据",
            "应付账款",
            "预收款项",
            "合同负债",
            "卖出回购金融资产款",
            "吸收存款及同业存放",
            "代理买卖证券款",
            "代理承销证券款",
            "应付职工薪酬",
            "应交税费",
            "其他应付款",
            "应付利息",
            "应付股利",
            "应付手续费及佣金",
            "应付分保账款",
            "持有待售负债",
            "一年内到期的非流动负债",
            "其他流动负债",
            "流动负债合计",
            "保险合同准备金",
            "长期借款",
            "应付债券",
            "租赁负债",
            "长期应付款",
            "长期应付职工薪酬",
            "预计负债",
            "递延收益",
            "递延所得税负债",
            "其他非流动负债",
            "非流动负债合计",
            "负债合计",
            "股本",
            "实收资本",
            "其他权益工具",
            "资本公积",
            "库存股",
            "其他综合收益",
            "专项储备",
            "盈余公积",
            "一般风险准备",
            "未分配利润",
            "归属于母公司所有者权益合计",
            "少数股东权益",
            "所有者权益合计",
            "负债和所有者权益总计",
            "营业总收入",
            "营业收入",
            "利息收入",
            "已赚保费",
            "手续费及佣金收入",
            "营业总成本",
            "营业成本",
            "利息支出",
            "手续费及佣金支出",
            "退保金",
            "赔付支出净额",
            "提取保险责任合同准备金净额",
            "保单红利支出",
            "分保费用",
            "税金及附加",
            "销售费用",
            "管理费用",
            "研发费用",
            "财务费用",
            "利息费用",
            "其他收益",
            "投资收益",
            "其中：对联营企业和合营企业的投资收益",
            "以摊余成本计量的金融资产终止确认收益",
            "汇兑收益",
            "净敞口套期收益",
            "公允价值变动收益",
            "信用减值损失",
            "资产减值损失",
            "资产处置收益",
            "营业利润",
            "营业外收入",
            "营业外支出",
            "利润总额",
            "所得税费用",
            "净利润",
            "按经营持续性分类",
            "持续经营净利润",
            "终止经营净利润",
            "按所有权归属分类",
            "归属于母公司所有者的净利润",
            "少数股东损益",
            "其他综合收益的税后净额",
            "归属母公司所有者的其他综合收益的税后净额",
            "不能重分类进损益的其他综合收益",
            "重新计量设定受益计划变动额",
            "权益法下不能转损益的其他综合收益",
            "其他权益工具投资公允价值变动",
            "企业自身信用风险公允价值变动",
            "其他",
            "将重分类进损益的其他综合收益",
            "权益法下可转损益的其他综合收益",
            "其他债权投资公允价值变动",
            "可供出售金融资产公允价值变动损益",
            "金融资产重分类计入其他综合收益的金额",
            "持有至到期投资重分类为可供出售金融资产损益",
            "其他债权投资信用减值准备",
            "现金流量套期储备",
            "外币财务报表折算差额",
            "其他",
            "归属于少数股东的其他综合收益的税后净额",
            "综合收益总额",
            "归属于母公司所有者的综合收益总额",
            "归属于少数股东的综合收益总额",
            "基本每股收益",
            "稀释每股收益",
            "销售商品、提供劳务收到的现金",
            "客户存款和同业存放款项净增加额",
            "向中央银行借款净增加额",
            "向其他金融机构拆入资金净增加额",
            "收到原保险合同保费取得的现金",
            "收到再保业务现金净额",
            "保户储金及投资款净增加额",
            "收取利息、手续费及佣金的现金",
            "拆入资金净增加额",
            "回购业务资金净增加额",
            "代理买卖证券收到的现金净额",
            "收到的税费返还",
            "收到其他与经营活动有关的现金",
            "经营活动现金流入小计",
            "购买商品、接受劳务支付的现金",
            "客户贷款及垫款净增加额",
            "存放中央银行和同业款项净增加额",
            "支付原保险合同赔付款项的现金",
            "拆出资金净增加额",
            "支付利息、手续费及佣金的现金",
            "支付保单红利的现金",
            "支付给职工以及为职工支付的现金",
            "支付的各项税费",
            "支付其他与经营活动有关的现金",
            "经营活动现金流出小计",
            "经营活动产生的现金流量净额",
            "收回投资收到的现金",
            "取得投资收益收到的现金",
            "处置固定资产、无形资产和其他长期资产收回的现金净额",
            "处置子公司及其他营业单位收到的现金净额",
            "收到其他与投资活动有关的现金",
            "投资活动现金流入小计",
            "购建固定资产、无形资产和其他长期资产支付的现金",
            "投资支付的现金",
            "质押贷款净增加额",
            "取得子公司及其他营业单位支付的现金净额",
            "支付其他与投资活动有关的现金",
            "投资活动现金流出小计",
            "投资活动产生的现金流量净额",
            "吸收投资收到的现金",
            "子公司吸收少数股东投资收到的现金",
            "取得借款收到的现金",
            "收到其他与筹资活动有关的现金",
            "筹资活动现金流入小计",
            "偿还债务支付的现金",
            "分配股利、利润或偿付利息支付的现金",
            "子公司支付给少数股东的股利、利润",
            "支付其他与筹资活动有关的现金",
            "筹资活动现金流出小计",
            "筹资活动产生的现金流量净额",
            "汇率变动对现金及现金等价物的影响",
            "现金及现金等价物净增加额",
            "期初现金及现金等价物余额",
            "期末现金及现金等价物余额",
        ]
        all_list = list1 + list2
        df2 = pd.DataFrame(columns=all_list)

        for file_name in file_names:
            txt_extracter = FinTableExtractor(file_name)
            results.append(txt_extracter.extract_fin_data())

        df2 = pd.DataFrame(results)
        df2.to_excel(self._tmp_excel_path + "/table_data_fin_info.xlsx", index=False)

        # process other col
        results = []
        df3 = pd.DataFrame(
            columns=[
                "文件名",
                "日期",
                "公司名称",
                "股票代码",
                "股票简称",
                "年份",
                "类型",
                "审计意见",
                "关键审计事项",
                "主要会计数据和财务指标",
                "主要销售客户",
                "主要供应商",
                "研发投入",
                "现金流",
                "资产及负债状况",
                "重大资产和股权出售",
                "主要控股参股公司分析",
                "公司未来发展的展望",
                "合并报表范围发生变化的情况说明",
                "聘任、解聘会计师事务所情况",
                "面临退市情况",
                "破产重整相关事项",
                "重大诉讼、仲裁事项",
                "处罚及整改情况",
                "公司及其控股股东、实际控制人的诚信状况",
                "重大关联交易",
                "重大合同及其履行情况",
                "重大环保问题",
                "社会责任情况",
                "公司董事、监事、高级管理人员变动情况",
                "公司员工情况",
                "非标准审计报告的说明",
                "公司控股股东情况",
                "审计报告",
                "全文",
            ]
        )

        for file_name in file_names:
            txt_extracter = FinTableExtractor(file_name)
            results.append(txt_extracter.extract_other_col())

        df3 = pd.DataFrame(results)
        df3.to_excel(self._tmp_excel_path + "/table_data_other_info.xlsx", index=False)

        # check if the three files have the same "文件名" column
        if (
            "文件名" not in df1.columns
            or "文件名" not in df2.columns
            or "文件名" not in df3.columns
        ):
            raise ValueError("One of the Excel files does not have the '文件名' column.")

        # merge to DataFrame
        df = df1.merge(df2, on="文件名", how="inner").merge(df3, on="文件名", how="inner")
        # to excel
        df.to_excel(
            self._tmp_excel_path + "/big_data_old.xlsx", engine="openpyxl", index=False
        )

        df["行业名称"] = ""

        new_name_list = {
            "营业成本率": {"公式": "营业成本率=营业成本/营业收入", "数值": ["营业成本", "营业收入"]},
            "投资收益占营业收入比率": {"公式": "投资收益占营业收入比率=投资收益/营业收入", "数值": ["投资收益", "营业收入"]},
            "管理费用率": {"公式": "管理费用率=管理费用/营业收入", "数值": ["管理费用", "营业收入"]},
            "财务费用率": {"公式": "财务费用率=财务费用/营业收入", "数值": ["财务费用", "营业收入"]},
            "三费比重": {
                "公式": "三费比重=(销售费用+管理费用+财务费用)/营业收入",
                "数值": ["销售费用", "管理费用", "财务费用", "营业收入"],
            },
            "企业研发经费占费用比例": {
                "公式": "企业研发经费占费用比例=研发费用/(销售费用+财务费用+管理费用+研发费用)",
                "数值": ["研发费用", "销售费用", "财务费用", "管理费用"],
            },
            "企业研发经费与利润比值": {"公式": "企业研发经费与利润比值=研发费用/净利润", "数值": ["研发费用", "净利润"]},
            "企业研发经费与营业收入比值": {"公式": "企业研发经费与营业收入比值=研发费用/营业收入", "数值": ["研发费用", "营业收入"]},
            "研发人员占职工人数比例": {
                "公式": "研发人员占职工人数比例=研发人员人数/职工总人数",
                "数值": ["研发人员人数", "职工总人数"],
            },
            "企业硕士及以上人员占职工人数比例": {
                "公式": "企业硕士及以上人员占职工人数比例=(硕士员工人数 + 博士及以上的员工人数)/职工总人数",
                "数值": ["硕士员工人数", "博士及以上的员工人数", "职工总人数"],
            },
            "毛利率": {"公式": "毛利率=(营业收入-营业成本)/营业收入", "数值": ["营业收入", "营业成本"]},
            "营业利润率": {"公式": "营业利润率=营业利润/营业收入", "数值": ["营业利润", "营业收入"]},
            "流动比率": {"公式": "流动比率=流动资产/流动负债", "数值": ["流动资产", "流动负债"]},
            "速动比率": {"公式": "速动比率=(流动资产-存货)/流动负债", "数值": ["流动资产", "存货", "流动负债"]},
            "资产负债比率": {"公式": "资产负债比率=总负债/资产总额", "数值": ["总负债", "资产总额"]},
            "现金比率": {"公式": "现金比率=货币资金/流动负债", "数值": ["货币资金", "流动负债"]},
            "非流动负债比率": {"公式": "非流动负债比率=非流动负债/总负债", "数值": ["非流动负债", "总负债"]},
            "流动负债比率": {"公式": "流动负债比率=流动负债/总负债", "数值": ["流动负债", "总负债"]},
            "净利润率": {"公式": "净利润率=净利润/营业收入", "数值": ["净利润", "营业收入"]},
        }
        for new_name in new_name_list:
            df[new_name] = ""

        # save the result
        df.to_excel(
            self._tmp_excel_path + "/table_data_final.xlsx",
            engine="openpyxl",
            index=False,
        )

        # set txt path
        txt_folder = self._tmp_dir_path + "/txt"
        # txt_folder = self._tmp_txt_path

        # get all the txt name
        txt_files = [file for file in os.listdir(txt_folder) if file.endswith(".txt")]

        # process txt
        for txt_file in tqdm(txt_files, desc="Processing txts"):
            # txt path
            txt_path = os.path.join(txt_folder, txt_file)

            # create txt dir
            folder_name = txt_file.split(".")[0]
            output_folder = os.path.join(self._tmp_excel_path, folder_name)
            os.makedirs(output_folder, exist_ok=True)
            print(txt_path)
            # create TableExtractor process txt file
            processor = FinTableProcessor(txt_path)
            processor.read_file()
            processor.process_text_data()
            processor.process_excel_data()
            processor.process_tables()
            processor.create_excel_files(output_folder)
            final_report_df = pd.read_excel(
                self._tmp_excel_path + "/table_data_final.xlsx"
            )
        print("process finished!")
        return final_report_df

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""
        return []

    def _save_all_text(self, all_text):
        directory = os.path.dirname(self._tmp_txt_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        for key in all_text.keys():
            with open(self._tmp_txt_path, "a+", encoding="utf-8") as file:
                file.write(json.dumps(all_text[key], ensure_ascii=False) + "\n")
        logger.info(f"save all text to txt {directory} file finished.")

    def as_retriever(self, top_k: int = 4, **kwargs) -> BaseRetriever:
        """Create a retriever.

        Args:
            top_k(int): default 4.

        Returns:
            EmbeddingRetriever
        """
        return EmbeddingRetriever(
            top_k=top_k,
            index_store=self._index_store,
            retrieve_strategy=self._retrieve_strategy,
        )
