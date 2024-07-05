"""ChatKnowledgeOperator."""
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    ModelMessage,
    ModelRequest,
    SystemPromptTemplate,
)
from dbgpt.core.awel import MapOperator

_DEFAULT_TEMPLATE_ZH = """基于以下给出的已知信息, 准守规范约束，专业、简要回答用户的问题.
规范约束:
    1.如果已知信息包含的图片、链接、表格、代码块等特殊markdown标签格式的信息，确保在答案中包含原文这些
    图片、链接、表格和代码标签，不要丢弃不要修改，如:图片格式：![image.png](xxx), 链接格式:
    [xxx](xxx), 表格格式:|xxx|xxx|xxx|, 代码格式:```xxx```.
    2.如果无法从提供的内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题" 禁止胡乱编造.
    3.回答的时候最好按照1.2.3.点进行总结.
    已知内容: 
    {context}
    问题:
    {question},请使用和用户相同的语言进行回答.
"""

_DEFAULT_TEMPLATE_EN = """Based on the known information below, provide users with 
professional and concise answers to their questions.
    constraints:
    1.Ensure to include original markdown formatting elements such as images, links, 
    tables, or code blocks without alteration in the response if they are present 
    in the provided information.For example, image format should be ![image.png](xxx), 
    link format [xxx](xxx), 
    table format should be represented with |xxx|xxx|xxx|, and code format with xxx.
    2.If the information available in the knowledge base is insufficient to answer the 
    question, state clearly: "The content provided in the knowledge base is not enough 
    to answer this question," and avoid making up answers.
    3.When responding, it is best to summarize the points in the order of 1, 2, 3.
        known information: 
        {context}
        question:
        {question},when answering, use the same language as the "user".
"""


class ChatKnowledgeOperator(MapOperator[ModelRequest, ModelRequest]):
    """ChatKnowledgeOperator."""

    def __init__(self, task_name="chat_knowledge", **kwargs):
        """ChatKnowledgeOperator."""
        self._knowledge_space = kwargs.pop("knowledge_space", None)
        super().__init__(task_name=task_name, **kwargs)

    async def map(self, input_value: ModelRequest) -> ModelRequest:
        """Map function for ChatKnowledgeOperator."""
        from dbgpt._private.config import Config
        from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
        from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        cfg = Config()

        user_input = input_value.messages[-1].content
        knowledge_name = self._knowledge_space
        if not knowledge_name:
            raise ValueError("Knowledge name is required.")

        embedding_factory = self.system_app.get_component(
            "embedding_factory", EmbeddingFactory
        )
        from dbgpt.rag.retriever.embedding import EmbeddingRetriever
        from dbgpt.serve.rag.connector import VectorStoreConnector

        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[cfg.EMBEDDING_MODEL]
        )

        config = VectorStoreConfig(
            name=knowledge_name,
            embedding_fn=embedding_fn,
        )
        vector_store_connector = VectorStoreConnector(
            vector_store_type=cfg.VECTOR_STORE_TYPE, vector_store_config=config
        )
        embedding_retriever = EmbeddingRetriever(
            top_k=5,
            index_store=vector_store_connector.client,
        )
        chunks = await embedding_retriever.aretrieve_with_scores(user_input, 0.3)
        context = "\n".join([doc.content for doc in chunks])

        input_values = {"context": context, "question": user_input}

        user_language = self.system_app.config.get_current_lang(default="en")
        prompt_template = (
            _DEFAULT_TEMPLATE_EN if user_language == "en" else _DEFAULT_TEMPLATE_ZH
        )
        prompt = ChatPromptTemplate(
            messages=[
                SystemPromptTemplate.from_template(prompt_template),
                HumanPromptTemplate.from_template("{question}"),
            ]
        )
        messages = prompt.format_messages(**input_values)
        model_messages = ModelMessage.from_base_messages(messages)
        request = input_value.copy()
        request.messages = model_messages
        return request
