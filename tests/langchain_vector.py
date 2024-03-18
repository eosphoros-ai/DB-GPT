# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/1/28 下午4:32
'''
import json
import os
from glob import glob
from operator import itemgetter


# 生成清空某个路径的代码
def create_clear_path(path):
    if os.path.exists(path):
        for file in glob(path + '/*'):
            os.remove(file)
    else:
        os.makedirs(path)


from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores.pgvector import PGVector, DistanceStrategy
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory

chunk_size = 300
chunk_overlap = 30
collection_name = 'atl_general_data_1_profile'

# embeddings_model = DefaultEmbeddingFactory().create(model_name='/datas/liab/embeddings_model/text2vec-large-chinese')
embeddings_model = DefaultEmbeddingFactory().create(model_name='/datas/liab/embeddings_model/stella-large-zh-v3-1792d')
CONNECTION_STRING = 'postgresql+psycopg2://fastgpt:1234@172.23.10.249:8100/newfastgpt'


def add_docs_to_pg():
    store = PGVector(
        collection_name=collection_name,
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings_model,
    )
    loader = TextLoader("/datas/liab/DB-GPT/docs/docs/awel.md")
    documents = loader.load()
    print(documents)
    text_splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    docs = text_splitter.split_documents(documents)
    store.add_documents(docs)


def write_to_pg(collection_name, glob_path):
    # collection_name = 'type3_qasamples_profile'
    # file_list = glob('/datas/liab/DB-GPT/tests/atl_data/type3/apart/*.txt')
    file_list = glob(glob_path)
    for file_path in file_list:
        loader = TextLoader(file_path)
        documents = loader.load()
        print(documents)
        text_splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        docs = text_splitter.split_documents(documents)
        db = PGVector.from_documents(
            embedding=embeddings_model,
            documents=docs,
            collection_name=collection_name,
            connection_string=CONNECTION_STRING,
        )


def query_from_pg():
    query = '''HR部门2024年1月加班情况'''
    collection_name = 'new_department_profile'
    db = PGVector(
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings_model,
        collection_name=collection_name,
        distance_strategy=DistanceStrategy.COSINE
    )
    corpus = []

    docs_with_score = db.similarity_search_with_score(query, k=6)
    docs_with_score.sort(key=itemgetter(1), reverse=True)
    for doc, score in docs_with_score:
        print("-" * 80)
        print("Score: ", score)
        print(doc.page_content)
        corpus.append(doc.page_content)
    return corpus


def score_normalize(data_list):
    max_value = max(data_list)
    min_value = min(data_list)
    return [(i - min_value) / (max_value - min_value) for i in data_list]


def calcuate_bm25(corpus, query):
    import jieba
    from rank_bm25 import BM25Okapi
    jieba.load_userdict("/datas/liab/DB-GPT/tests/userdict.txt")
    stop_words = [' ', '\t', '\n']
    with open('/datas/liab/DB-GPT/tests/stopwords.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                stop_words.append(line)

    tokenizerd_query = [jiebaword.upper() for jiebaword in list(jieba.cut(query)) if jiebaword not in stop_words]
    # print('tokenizerd_query',tokenizerd_query)
    tokenized_corpus = [[jiebaword.upper() for jiebaword in list(jieba.cut(doc)) if jiebaword not in stop_words] for doc
                        in corpus]
    # print('tokenized_corpus',tokenized_corpus)
    bm25 = BM25Okapi(tokenized_corpus)
    doc_scores = bm25.get_scores(tokenizerd_query)
    return score_normalize(doc_scores)


def query_from_pg_bm25():
    query = '''ATL的经理有多少位？'''
    collection_name = 'new_department_profile'
    collection_name = 'type2_general_profile'
    collection_name = 'hr_chinese_fk_profile'
    db = PGVector(
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings_model,
        collection_name=collection_name
    )

    docs_with_score = db.similarity_search_with_score(query, k=30)
    corpus = []
    for doc, score in docs_with_score:
        corpus.append(doc.page_content)
    doc_scores = calcuate_bm25(corpus, query)

    for doc, score in zip(corpus, doc_scores):
        print(doc, score)
        if float(score) > 0.7:
            pass


def delete_from_pg(del_collection_name):
    # del_collection_name = 'type2_general_profile'
    db = PGVector(
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings_model,
        collection_name=del_collection_name
    )
    db.delete_collection()
    print(f'{del_collection_name}  already deleted')


def split_data_to_path():
    data_list = [
        ('general_knowledge', 'general'),
        ('一级机构说明', 'department'),
        ('三级机构说明', 'department'),
        ('二级机构说明', 'department'), ]
    for data_path, new_path in data_list:
        with open(f'/datas/liab/DB-GPT/tests/atl_data/type1/{data_path}.txt', 'r') as f:
            conten = f.readlines()
        print(conten)
        create_clear_path(f'/datas/liab/DB-GPT/tests/atl_data/type2/{new_path}/')
        for ii, con in enumerate(conten):
            print(con)

            with open('/datas/liab/DB-GPT/tests/atl_data/type2/%s/%s.txt' % (new_path, ii), 'w') as f:
                f.write(con.strip('\n').strip(',') + '\n')
    get_qa_samples()


def get_qa_samples():
    with open('/datas/liab/DB-GPT/tests/atl_data/type3/qa_samples.jsonl', 'r') as f:
        contents = f.read()

    for ii, con in enumerate(eval(contents)):
        print(con)

        with open('/datas/liab/DB-GPT/tests/atl_data/type3/apart/%s.txt' % ii, 'w') as f:
            f.write(con['user_input'])


def qa_sample_to_dict():
    with open('/datas/liab/DB-GPT/tests/atl_data/type3/qa_samples.jsonl', 'r') as f:
        contents = f.read()
    temp_dict = {}
    for ii, con in enumerate(eval(contents)):
        temp_dict[con['user_input']] = con['sql']
    with open('/datas/liab/DB-GPT/tests/atl_data/type3/qa_samples.json', 'w') as f:
        json.dump(temp_dict, f, ensure_ascii=False, indent=4)


def init_delete_all_collection():
    '''
    re_init data
    '''
    # split general data & qa samples
    split_data_to_path()
    collection_list = [
        ('atl_general_data_1_profile', '/datas/liab/DB-GPT/tests/atl_data/type1/*.txt'),
        ('type2_general_profile', '/datas/liab/DB-GPT/tests/atl_data/type2/general/*.txt'),
        ('type3_qasamples_profile', '/datas/liab/DB-GPT/tests/atl_data/type3/apart/*.txt'),  # QA sample对
        ('type2_department_profile', '/datas/liab/DB-GPT/tests/atl_data/type2/department/*.txt'),
        ('new_department_profile', '/datas/liab/DB-GPT/tests/atl_data/type2/new_department/*.txt'),
    ]
    for cl in collection_list:
        delete_from_pg(cl[0])
        write_to_pg(cl[0], cl[1])


def bm25test():
    corpus = [
        """a_sap_performance_ai(编制年度 (公司财年), 姓名, 人员工号, 绩效 (绩效排序（好->差）:["A","B+","B","B-","C","D"])), and table comment: 这个是公司每个员工每个财年的绩效表""",
        """a_sap_staffing_recruitment_plan_chinese(编制年度 (公司的财年，值为"TXXX",其中XXX是数字，例如:["T126","T127","T128"]), 编制月度 (公司财年中的月度，值有:[1,2,3,4,...,12]), 员工子组 (员工等级组别，值有["A1","A2","A3","A4","A5"]，其中A5级别最高), 有效编制空缺, 创建日期, 年度可申请空缺数量, 季度可申请空缺数量, 月度可申请空缺数量, 年度编制数量, 季度编制数量, 月度编制数量, 特批编制数量, 拟在职人数, 有效但是没有报到空缺数, 写入日期, open数, 关闭数, 冻结数, 集团名称, 一级机构 (也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等), 二级机构 (也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等), 职级范围), and table comment: 这个是公司各个部门（一级机构），小组（二级机构、三级机构），在每个编制年度(财年)/编制月度的招聘计划表。""",
        """a_sap_employee_education_experience_chinese(人员工号 (每个员工的唯一工号，也是这张表的主键), 姓名, 开始日期 (受教育的开始日期), 结束日期 (受教育的结束日期), 学历 (值：["硕士","高中","大学专科","博士","初中及以下","大学本科","中专"]), 教育类型, 院校_培训机构, 国家, 证书, 第一专业), and table comment: 这个是公司每个员工受教育经历的数据表。""",
        """a_sap_reporting_relationship_chinese(开始日期 (汇报关系开始的时间), 结束日期 (汇报关系结束的时间), 人员工号 (该表主键，每个员工的唯一id值。), 姓名, 入司日期, 工作性质 (值为：["全职-计算","挂职","兼职-不计算","劳务外包"]), 一级机构 (也称为部门，值一般为英文字母组成，例如：["idt","apd","hr","qa","fe"]等), 二级机构 (也称为组，是部门下分组，例如：["ai","ad","cpa","ta"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["emc","ipqc","ph","ep-m"]等等), 是否管理机构 (该员工是否是部门（一级机构），小组（二级机构，三级机构）负责人。值为：["是","否"]), 主管1姓名, 主管1职位, 主管1职务, 主管2姓名, 主管2职位, 主管2职务, 经理1姓名, 经理1职位, 经理1职务, 经理2姓名, 经理2职位, 经理2职务, 经理3姓名, 经理3职位, 经理3职务, 经理4姓名, 经理4职位, 经理4职务, 总监1姓名, 总监1职位, 总监1职务, 总监2姓名, 总监2职位, 总监2职务, 总监3姓名, 总监3职位, 总监3职务, 总监4姓名, 总监4职位, 总监4职务, 一级机构负责人姓名, 一级机构负责人职位, 一级机构负责人职务), and table comment: 这个是公司每个员工汇报关系表。""",
        """a_sap_positions_responsibilities_risks_chinese(集团, 一级机构 (也称为部门，值一般为英文字母组成，例如：["idt","apd","hr","qa","fe"]等), 二级机构 (也称为组，是部门下分组，例如：["ai","ad","cpa","ta"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["emc","ipqc","ph","ep-m"]等等), 职位, 成本类别名称 (岗位的成本类别，值有：["mgr.above","idl","staff","dl"]), 岗位名称, 岗位属性名称, 角色定位, 岗位风险点, 岗位职责, 岗位任职资格, 绩效贡献, 经验及其他资质要求, 部门职能类型名称 (值有：["工程","研发","运营","支持","销售","质量","其它","atl"]), 职务, 职务类型 (值为：["p1-技术类","f4-文职类","技术类","实习","f2-操作类","p2-非技术类","m-管理类","f3-现场管理类","f1-现场技术类"]), 现职人数), and table comment: 这个是公司每个岗位的责任和风险，以及绩效贡献标准等等表。""",
        """a_sap_employee_information_chinese(人员工号 (每个员工的唯一工号，也是这张表的主键), 姓名, 雇佣状态 (值为：["在职","离职"]), 职位, 入职日期, 部门负责人 (该员工所属部门（一级机构）的负责人姓名), 人事范围 (值为：["Ampack-DG","SSL","SZ","Poweramp","Ampack","BM","HK","ND","Ampace"]), 员工组 (值为：["劳务外包","试用","退休返聘","CJR","劳务派遣-正式","正式","劳务派遣-试用","顾问","实习"]), 员工子组文本 (值为：["顾问","实习","二级员工","五级员工","一级员工","三级员工","CJR","四级员工"]), 上班地点 (值为：["SSL","SZ(深圳)","WX(无锡)","XM","IN","BM","HK","SG","MNO","ND","SSL-P"]), 英文名, 性别, 国籍, 民族, 籍贯, 身份证地址的省_直辖市, 开始参加工作日期, 员工本人联系号码, 一级机构 (也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等), 二级机构 (也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等), 职务名称, 员工工作性质文本 (值为：["兼职-不计算","劳务外包","兼职-计算","全职-计算","挂职"]), 直属上司工号, 直属上司姓名, 集团入职日期), and table comment: 这个是公司每个员工基本信息表。"""
    ]
    query = "在当前年份（2023年）中，哪个一级机构的员工平均绩效得分最低？请列出该机构的名称及其平均绩效得分，并且请考虑到绩效得分'A'到'D'依次递减。"
    res_socre_normalize = calcuate_bm25(corpus, query)
    docs_with_score = [(doc, score) for doc, score in zip(corpus, res_socre_normalize)]
    docs_with_score.sort(key=itemgetter(1), reverse=True)

    # 一个数据列表做归一化

    docs_result = []
    for doc, score in docs_with_score:
        print("-" * 80)
        print("Score: ", score)
        print(doc)
        if score > 0:
            docs_result.append(doc)
        print('=======================')

    return docs_result


def langchain_bm25():
    from langchain.retrievers import BM25Retriever
    corpus = [
        """a_sap_performance_ai(编制年度 (公司财年), 姓名, 人员工号, 绩效 (绩效排序（好->差）:["A","B+","B","B-","C","D"])), and table comment: 这个是公司每个员工每个财年的绩效表""",
        """a_sap_staffing_recruitment_plan_chinese(编制年度 (公司的财年，值为"TXXX",其中XXX是数字，例如:["T126","T127","T128"]), 编制月度 (公司财年中的月度，值有:[1,2,3,4,...,12]), 员工子组 (员工等级组别，值有["A1","A2","A3","A4","A5"]，其中A5级别最高), 有效编制空缺, 创建日期, 年度可申请空缺数量, 季度可申请空缺数量, 月度可申请空缺数量, 年度编制数量, 季度编制数量, 月度编制数量, 特批编制数量, 拟在职人数, 有效但是没有报到空缺数, 写入日期, open数, 关闭数, 冻结数, 集团名称, 一级机构 (也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等), 二级机构 (也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等), 职级范围), and table comment: 这个是公司各个部门（一级机构），小组（二级机构、三级机构），在每个编制年度(财年)/编制月度的招聘计划表。""",
        """a_sap_employee_education_experience_chinese(人员工号 (每个员工的唯一工号，也是这张表的主键), 姓名, 开始日期 (受教育的开始日期), 结束日期 (受教育的结束日期), 学历 (值：["硕士","高中","大学专科","博士","初中及以下","大学本科","中专"]), 教育类型, 院校_培训机构, 国家, 证书, 第一专业), and table comment: 这个是公司每个员工受教育经历的数据表。""",
        """a_sap_reporting_relationship_chinese(开始日期 (汇报关系开始的时间), 结束日期 (汇报关系结束的时间), 人员工号 (该表主键，每个员工的唯一id值。), 姓名, 入司日期, 工作性质 (值为：["全职-计算","挂职","兼职-不计算","劳务外包"]), 一级机构 (也称为部门，值一般为英文字母组成，例如：["idt","apd","hr","qa","fe"]等), 二级机构 (也称为组，是部门下分组，例如：["ai","ad","cpa","ta"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["emc","ipqc","ph","ep-m"]等等), 是否管理机构 (该员工是否是部门（一级机构），小组（二级机构，三级机构）负责人。值为：["是","否"]), 主管1姓名, 主管1职位, 主管1职务, 主管2姓名, 主管2职位, 主管2职务, 经理1姓名, 经理1职位, 经理1职务, 经理2姓名, 经理2职位, 经理2职务, 经理3姓名, 经理3职位, 经理3职务, 经理4姓名, 经理4职位, 经理4职务, 总监1姓名, 总监1职位, 总监1职务, 总监2姓名, 总监2职位, 总监2职务, 总监3姓名, 总监3职位, 总监3职务, 总监4姓名, 总监4职位, 总监4职务, 一级机构负责人姓名, 一级机构负责人职位, 一级机构负责人职务), and table comment: 这个是公司每个员工汇报关系表。""",
        """a_sap_positions_responsibilities_risks_chinese(集团, 一级机构 (也称为部门，值一般为英文字母组成，例如：["idt","apd","hr","qa","fe"]等), 二级机构 (也称为组，是部门下分组，例如：["ai","ad","cpa","ta"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["emc","ipqc","ph","ep-m"]等等), 职位, 成本类别名称 (岗位的成本类别，值有：["mgr.above","idl","staff","dl"]), 岗位名称, 岗位属性名称, 角色定位, 岗位风险点, 岗位职责, 岗位任职资格, 绩效贡献, 经验及其他资质要求, 部门职能类型名称 (值有：["工程","研发","运营","支持","销售","质量","其它","atl"]), 职务, 职务类型 (值为：["p1-技术类","f4-文职类","技术类","实习","f2-操作类","p2-非技术类","m-管理类","f3-现场管理类","f1-现场技术类"]), 现职人数), and table comment: 这个是公司每个岗位的责任和风险，以及绩效贡献标准等等表。""",
        """a_sap_employee_information_chinese(人员工号 (每个员工的唯一工号，也是这张表的主键), 姓名, 雇佣状态 (值为：["在职","离职"]), 职位, 入职日期, 部门负责人 (该员工所属部门（一级机构）的负责人姓名), 人事范围 (值为：["Ampack-DG","SSL","SZ","Poweramp","Ampack","BM","HK","ND","Ampace"]), 员工组 (值为：["劳务外包","试用","退休返聘","CJR","劳务派遣-正式","正式","劳务派遣-试用","顾问","实习"]), 员工子组文本 (值为：["顾问","实习","二级员工","五级员工","一级员工","三级员工","CJR","四级员工"]), 上班地点 (值为：["SSL","SZ(深圳)","WX(无锡)","XM","IN","BM","HK","SG","MNO","ND","SSL-P"]), 英文名, 性别, 国籍, 民族, 籍贯, 身份证地址的省_直辖市, 开始参加工作日期, 员工本人联系号码, 一级机构 (也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等), 二级机构 (也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等), 三级机构 (也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等), 职务名称, 员工工作性质文本 (值为：["兼职-不计算","劳务外包","兼职-计算","全职-计算","挂职"]), 直属上司工号, 直属上司姓名, 集团入职日期), and table comment: 这个是公司每个员工基本信息表。"""
    ]
    query = "找出当前在职的员工中持有'硕士'学历但未在技术类职务工作的员工姓名和职务名称，并且统计这样的员工数量。"
    retriever = BM25Retriever.from_texts(corpus)
    from langchain_core.documents import Document
    print(retriever.get_relevant_documents(query))


def reranker():
    from FlagEmbedding import FlagReranker
    reranker = FlagReranker('/datas/liab/rerank_model/bge-reranker-large', use_fp16=True)
    score = reranker.compute_score()


def rrf_ranker(bm25_docs, embedding_docs, weights=[0.5, 0.5], c=60, topk=6):
    doc_lists = [bm25_docs, embedding_docs]
    all_documents = set()
    for doc_list in doc_lists:
        for doc in doc_list:
            all_documents.add(doc)

    # Initialize the RRF score dictionary for each document
    rrf_score_dic = {doc: 0.0 for doc in all_documents}

    # Calculate RRF scores for each document
    for doc_list, weight in zip(doc_lists, weights):
        for rank, doc in enumerate(doc_list, start=1):
            rrf_score = weight * (1 / (rank + c))
            rrf_score_dic[doc] += rrf_score

    # Sort documents by their RRF scores in descending order
    sorted_documents = sorted(rrf_score_dic.items(), key=itemgetter(1), reverse=True)
    data = [score for text, score in sorted_documents[:topk]]

    # 计算平均值
    average = sum(data) / len(data)

    result = []
    for sorted_doc in sorted_documents[:topk]:
        text, score = sorted_doc
        if score > average:
            node_with_score = (score, text)
            result.append(node_with_score)
            print(node_with_score)

    # print(result)
    return result


if __name__ == '__main__':
    # delete_from_pg()
    init_delete_all_collection()
    #
    # print('embedding')
    # embedding_docs = query_from_pg()
    #
    # print('bm25')
    # bm25_docs = bm25test()
    #
    # print('rrf ranker')
    # print(rrf_ranker(bm25_docs, embedding_docs))
    # langchain_bm25()
    # split_data_to_path()
    # query_from_pg()
    # query_from_pg_bm25()
    # write_to_pg()
    # qa_sample_to_dict()
    # add_docs_to_pg()
    # get_qa_samples()
    # write_to_pg('new_department_profile','/datas/liab/DB-GPT/tests/atl_data/type2/new_department/*.md')
