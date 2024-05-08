"""Elasticsearch vector store"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable, List, Optional

from dbgpt._private.pydantic import Field
from dbgpt.core import Chunk, Embeddings
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import FilterOperator, MetadataFilters
from dbgpt.util import string_utils
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)

try:
    import jieba
    import jieba.analyse 
    from langchain.schema import Document
    from langchain.vectorstores.elasticsearch import ElasticsearchStore
    from elasticsearch import Elasticsearch 
except ImportError:
    raise ValueError(
        "Could not import elasticsearch AND jieba python package. "
        "Please install it with `pip install elasticsearch`."
        "Please install it with `pip install jieba`."
    )  


@register_resource(
    _("ElasticSearch Vector Store"),
    "elasticsearch_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("Uri"),
            "uri",
            str,
            description=_(
                "The uri of elasticsearch store, if not set, will use the default " "uri."
            ),
            optional=True,
            default="localhost",
        ),
        Parameter.build_from(
            _("Port"),
            "port",
            str,
            description=_(
                "The port of elasticsearch store, if not set, will use the default " "port."
            ),
            optional=True,
            default="9200",
        ),
        Parameter.build_from(
            _("Alias"),
            "alias",
            str,
            description=_(
                "The alias of elasticsearch store, if not set, will use the default " "alias."
            ),
            optional=True,
            default="default",
        ),
        Parameter.build_from(
            _("Index Name"),
            "index_name",
            str,
            description=_(
                "The index name of elasticsearch store, if not set, will use the "
                "default index name."
            ),
            optional=True,
            default="index_name_test",
        ),  
    ],
    description=_("Elasticsearch vector store."),
)
class ElasticsearchVectorConfig(VectorStoreConfig):
    """Elasticsearch vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    uri: str = Field(
        default="localhost",
        description="The uri of elasticsearch store, if not set, will use the default uri.",
    )
    port: str = Field(
        default="9200",
        description="The port of elasticsearch store, if not set, will use the default port.",
    )

    alias: str = Field(
        default="default",
        description="The alias of elasticsearch store, if not set, will use the default "
        "alias.",
    )
    index_name: str = Field(
        default="index_name_test",
        description="The index name of elasticsearch store, if not set, will use the "
        "default index name.",
    )  
    metadata_field: str = Field(
        default="metadata",
        description="The metadata field of elasticsearch store, if not set, will use the "
        "default metadata field.",
    )
    secure: str = Field(
        default="",
        description="The secure of elasticsearch store, if not set, will use the default "
        "secure.",
    )


class ElasticStore(VectorStoreBase):
    """Elasticsearch vector store."""

    def __init__(self, vector_store_config: ElasticsearchVectorConfig) -> None:
        """Create a ElasticsearchStore instance.

        Args:
            vector_store_config (ElasticsearchVectorConfig): ElasticsearchStore config. 
        """

        connect_kwargs = {}
        elasticsearch_vector_config = vector_store_config.dict()
        self.uri = elasticsearch_vector_config.get("uri") or os.getenv("ElasticSearch_URL", "localhost")
        self.port = elasticsearch_vector_config.get("post") or os.getenv("ElasticSearch_PORT", "9200")
        self.username = elasticsearch_vector_config.get("username") or os.getenv("ElasticSearch_USERNAME")
        self.password = elasticsearch_vector_config.get("password") or os.getenv("ElasticSearch_PASSWORD") 

        self.collection_name = (
            elasticsearch_vector_config.get("name") or vector_store_config.name
        )
        ### 同milvus,目前只支持全中文、英文+数字的命名形式，若是全中文会转换成英文+数字的命名形式
        ### 同时es索引只支持小写字符。
        if string_utils.is_all_chinese(self.collection_name):
            bytes_str = self.collection_name.encode("utf-8")
            hex_str = bytes_str.hex()
            self.collection_name = hex_str
        if vector_store_config.embedding_fn is None:
            # Perform runtime checks on self.embedding to
            # ensure it has been correctly set and loaded
            raise ValueError("embedding_fn is required for ElasticSearchStore")
        ### 同时es索引只支持小写字符。
        self.index_name = self.collection_name.lower()
        self.embedding: Embeddings = vector_store_config.embedding_fn
        self.fields: List = [] 

        if (self.username is None) != (self.password is None):
            raise ValueError(
                "Both username and password must be set to use authentication for "
                "ElasticSearch"
            )

        if self.username:
            connect_kwargs["username"] = self.username
            connect_kwargs["password"] = self.password
 
        # 创建索引的配置===单节点情况下，多节点情况下可设置副本数随意。
        self.index_settings = { "settings": {
                                "number_of_shards": 1,
                                "number_of_replicas": 0  # 设置副本数量为0
                        }}

        """"""
        # ES python客户端连接（仅连接）
        try:
            if self.username != "" and self.password != "":
                self.es_client_python = Elasticsearch(f"http://{self.uri}:{self.port}",
                                                        basic_auth=(self.username,self.password))                 
                # 创建索引，报错--先忽略
                if not self.vector_name_exists():
                    self.es_client_python.indices.create(index=self.index_name, body=self.index_settings)
            else:
                logger.warning("ES未配置用户名和密码")
                self.es_client_python = Elasticsearch(f"http://{self.uri}:{self.port}")
                if not self.vector_name_exists():
                    self.es_client_python.indices.create(index=self.index_name, body=self.index_settings)
        except ConnectionError:
            logger.error("连接到 Elasticsearch 失败！")
        except Exception as e:
            logger.error(f"ES python客户端连接（仅连接）===Error 发生 : {e}")

        # langchain ES 连接、创建索引
        try: 
            if self.username != "" and self.password != "":
                self.db_init = ElasticsearchStore(
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    query_field="context",
                    vector_query_field="dense_vector",
                    embedding=self.embedding,
                    es_user=self.username,
                    es_password=self.password
                )
            else: 
                logger.warning("ES未配置用户名和密码")
                self.db_init = ElasticsearchStore(
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    query_field="context",
                    vector_query_field="dense_vector",
                    embedding=self.embedding,
                )            
        except ConnectionError:
            print("### 连接到 Elasticsearch 失败！")
            logger.error("### 连接到 Elasticsearch 失败！")
        except Exception as e:
            logger.error(f"langchain ES 连接、创建索引===Error 发生 : {e}")
        

    def load_document(
        self,
        #docs: Iterable[str],   
        chunks: List[Chunk]
    ) -> List[str]: 
        """Add text data into ElastcSearch.
        将docs写入到ES中
        """
        logger.info("ElasticStore load document")
        try: 
            texts = [chunk.content for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]
            ids = [chunk.chunk_id for chunk in chunks]
            if self.username != "" and self.password != "":
                #logger.info(f"wwt docs metadatas[0] === ElasticsearchStore.from_texts:::{metadatas[0]}: len={len(metadatas)}")
                self.db = ElasticsearchStore.from_texts(
                    texts=texts,
                    embedding=self.embedding,
                    metadatas=metadatas,
                    ids=ids,
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    distance_strategy="COSINE",  # Defaults to COSINE. Can be one of COSINE, EUCLIDEAN_DISTANCE, or DOT_PRODUCT.
                    query_field="context",  ## Name of the field to store the texts in.
                    vector_query_field="dense_vector", # Optional. Name of the field to store the embedding vectors in.
                    #verify_certs=False,
                    # strategy: Optional. Retrieval strategy to use when searching the index.
                    # Defaults to ApproxRetrievalStrategy. 
                    # Can be one of ExactRetrievalStrategy, ApproxRetrievalStrategy, or SparseRetrievalStrategy.
                    es_user=self.username,
                    es_password=self.password,
                ) 
                logger.info(f"Embedding success.......")
            else:
                self.db = ElasticsearchStore.from_documents(
                    texts=texts,
                    embedding=self.embedding,
                    metadatas=metadatas,
                    ids=ids,
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    distance_strategy="COSINE",
                    query_field="context",
                    vector_query_field="dense_vector",
                    #verify_certs=False, 
                    ) 
            return ids
        except ConnectionError as ce: 
            logger.error(f"连接到 Elasticsearch 失败！{ce}")
        except Exception as e:
            logger.error(f"ES load_document 时 Error 发生 : {e}") 


    def delete_by_ids(self, ids):
        """Delete vector by ids."""
        #logger.info(f"1begin delete elasticsearch len ids: {len(ids)}") 
        #logger.info(f"1begin delete elasticsearch type ids: {type(ids)}") 
        ids = ids.split(",")
        #logger.info(f"2begin delete elasticsearch len ids: {len(ids)}") 
        #logger.info(f"2begin delete elasticsearch type ids: {type(ids)}") 
        #es_client= self.db_init.connect_to_elasticsearch(
        #        es_url=f"http://{self.uri}:{self.port}",  
        #        es_user=self.username,
        #        es_password=self.password,   
        #)
        try:
            self.db_init.delete(ids=ids)  
            self.es_client_python.indices.refresh(index=self.index_name)
        except Exception as e:
            logger.error(f"Error 发生 : {e}") 
            

    def similar_search(
        self, text: str, topk: int, score_threshold: float, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Perform a search on a query string and return results. 
        """
        query = text
        print(
            f" similar_search 输入的query参数为:{query}") 
        query_list = jieba.analyse.textrank(query, topK=20, withWeight=False)
        if len(query_list) == 0:
            query_list = [query]
        body = {
            "query": {
                "match": {
                    "context": " ".join(query_list)
                }
            }
        }
        search_results = self.es_client_python.search(index=self.index_name, body=body, size=topk)
        search_results = search_results['hits']['hits']

        # 判断搜索结果是否为空
        if not search_results:
            return []
        
        info_docs = []
        byte_count = 0

        for result in search_results:
            index_name = result["_index"]  
            vector_doc = result["dense_vector"]  # 文本的稠密向量表示
            doc_id = result["_id"]  
            source = result["_source"]
            context = source["context"]
            metadata = source["metadata"]
            score = result["_score"]

            # 如果下一个context会超过总字节数限制，则截断context
            VS_TYPE_PROMPT_TOTAL_BYTE_SIZE = 3000   ### 每种向量库的prompt字节的最大长度，超过则截断，后面放到.env中
            if (byte_count + len(context)) > VS_TYPE_PROMPT_TOTAL_BYTE_SIZE:
                context = context[:VS_TYPE_PROMPT_TOTAL_BYTE_SIZE - byte_count]

            doc_with_score = [Document(page_content=context, metadata=metadata), score, doc_id]
            info_docs.append(doc_with_score)

            byte_count += len(context)

            # 如果字节数已经达到限制，则结束循环
            if byte_count >= VS_TYPE_PROMPT_TOTAL_BYTE_SIZE:
                break
        print(f"ES搜索到{len(info_docs)}个结果：")
        # 将结果写入文件
        result_file = open("es_search_results.txt", "w", encoding="utf-8")
        result_file.write(f"query:{query}")
        result_file.write(f"ES搜索到{len(info_docs)}个结果：\n")
        for item in info_docs:
            doc = item[0]
            result_file.write(doc.page_content + "\n")
            result_file.write("*" * 20)
            result_file.write("\n")
            result_file.flush()
            print(doc.page_content + "\n")
            print("*" * 20)
            print("\n")
        result_file.close()

        return [
            Chunk(
                metadata=json.loads(doc.metadata.get("metadata", "")),
                content=doc.page_content,
            )
            for doc, score, id  in info_docs
        ]


    def similar_search_with_scores(
        self, text, topk, score_threshold, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Perform a search on a query string and return results with score.

        For more information about the search parameters, take a look at the ElasticSearch
        documentation found here: https://www.elastic.co/

        Args:
            text (str): The query text.
            topk (int): The number of similar documents to return.
            score_threshold (float): Optional, a floating point value between 0 to 1.
            filters (Optional[MetadataFilters]): Optional, metadata filters.
        Returns:
            List[Tuple[Document, float]]: Result doc and score.
        """ 

        query = text
        query_list = jieba.analyse.textrank(query, topK=20, withWeight=False)
        logger.info(f"similar_search 输入的 query 参数为:{query}") 
        logger.info(f"similar_search jieba算法后输入的 query_list 参数为:{query_list}") 
        if len(query_list) == 0:
            query_list = [query]
        body = {
            "query": {
                "match": {
                    "context": " ".join(query_list)
                }
            }
        }
        search_results = self.es_client_python.search(index=self.index_name, body=body, size=topk)
        search_results = search_results['hits']['hits']
        # 判断搜索结果是否为空
        if not search_results:
            return []
        
        info_docs = []
        byte_count = 0

        for result in search_results:            
            # logger.info(f"wwt add query result==={result}")
            ## 全部列出了
            index_name = result["_index"]  
            #vector_doc = result["dense_vector"]  # 文本的稠密向量表示
            doc_id = result["_id"]  
            source = result["_source"] #  源头
            context = source["context"]  # 文本内容
            metadata = source["metadata"]  ## 文本来源路径
            result["_score"] = result["_score"] / 100  # 分数，100分zhi
            score = result["_score"]   

            # 如果下一个context会超过总字节数限制，则截断context
            VS_TYPE_PROMPT_TOTAL_BYTE_SIZE = 3000   ### 每种向量库的prompt字节的最大长度，超过则截断，后面放到.env中
            if (byte_count + len(context)) > VS_TYPE_PROMPT_TOTAL_BYTE_SIZE:
                context = context[:VS_TYPE_PROMPT_TOTAL_BYTE_SIZE - byte_count]

            doc_with_score = [Document(page_content=context, metadata=metadata), score, doc_id]
            info_docs.append(doc_with_score)

            byte_count += len(context)

            # 如果字节数已经达到限制，则结束循环
            if byte_count >= VS_TYPE_PROMPT_TOTAL_BYTE_SIZE:
                break
        print(f"ES搜索到{len(info_docs)}个结果：")
        logger.info(f"ES搜索到{len(info_docs)}个结果：")
        # 将结果写入文件
        result_file = open("es_search_results.txt", "w", encoding="utf-8")
        result_file.write(f"query:{query} \n")
        result_file.write(f"ES搜索到{len(info_docs)}个结果：\n")
        for item in info_docs:
            doc = item[0]
            result_file.write(doc.page_content + "\n")
            result_file.write("*" * 50)
            result_file.write("\n")
            result_file.flush()
            print(doc.page_content + "\n")
            print("*" * 50)
            print("\n\n")
        result_file.close()
         
        if any(score < 0.0 or score > 1.0 for _, score, _ in info_docs):
            logger.warning(
                "similarity score need between" f" 0 and 1, got {info_docs}"
            )

        logger.info(f"wwt add score_threshold: {score_threshold}")
        if score_threshold is not None:
            ## for test
            scorel = [score for doc, score, id in info_docs]
            logger.info(f"wwt add score_threshold: {score_threshold}")
            logger.info(f"wwt add score list now: {scorel}")
            docs_and_scores = [
                Chunk(
                    metadata=doc.metadata,
                    content=doc.page_content,
                    score=score,
                    chunk_id=id,
                )
                for doc, score, id in info_docs
                if score >= score_threshold
            ]
            if len(docs_and_scores) == 0:
                logger.warning(
                    "No relevant docs were retrieved using the relevance score"
                    f" threshold {score_threshold}"
                )
        return docs_and_scores
 

    def vector_name_exists(self):
        """Whether vector name exists.""" 
        """is vector store name exist."""
        return self.es_client_python.indices.exists(index=self.index_name)
    

    def delete_vector_name(self, vector_name: str):
        """Delete vector name/index_name."""  
        """从知识库(知识库名的小写部分)删除全部向量"""
        if self.es_client_python.indices.exists(index=self.index_name):
            self.es_client_python.indices.delete(index=self.index_name)
            #self.es_client_python.indices.delete(index=self.kb_name)

"""
    def delete_by_ids(self, kb_file,):
        ### Delete vector by index_name. 
        try:
            if self.es_client_python.indices.exists(index=self.index_name):
                # 从向量数据库中删除索引(文档名称是Keyword)
                query = {
                    "query": {
                        "term": {
                            "metadata.source.keyword": kb_file.filepath
                        }
                    }
                }
                # 注意设置size，默认返回10个。
                search_results = self.es_client_python.search(body=query, size=50)
                delete_list = [hit["_id"]
                               for hit in search_results['hits']['hits']]
                if len(delete_list) == 0:
                    return None
                else:
                    for doc_id in delete_list:
                        try:
                            logger.info(f"elasticsearch self.index_name:{self.index_name} begin delete...") 
                            self.es_client_python.delete(index=self.index_name,
                                                         id=doc_id,
                                                         refresh=True)
                        except Exception as e:
                            logger.error("ES Docs Delete Error!")

                # self.db_init.delete(ids=delete_list)
                # self.es_client_python.indices.refresh(index=self.index_name)
        except Exception as e:
            logger.error(f"Error 发生 : {e}")
            return None 
        return True
 
"""