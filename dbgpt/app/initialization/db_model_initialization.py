"""Import all models to make sure they are registered with SQLAlchemy.
"""
from dbgpt.agent.db.my_plugin_db import MyPluginEntity
from dbgpt.agent.db.plugin_hub_db import PluginHubEntity
from dbgpt.app.knowledge.chunk_db import DocumentChunkEntity
from dbgpt.app.knowledge.document_db import KnowledgeDocumentEntity
from dbgpt.app.knowledge.space_db import KnowledgeSpaceEntity
from dbgpt.app.openapi.api_v1.feedback.feed_back_db import ChatFeedBackEntity

from dbgpt.serve.prompt.models.models import ServeEntity as PromptManageEntity
from dbgpt.datasource.manages.connect_config_db import ConnectConfigEntity
from dbgpt.storage.chat_history.chat_history_db import (
    ChatHistoryEntity,
    ChatHistoryMessageEntity,
)

_MODELS = [
    PluginHubEntity,
    MyPluginEntity,
    PromptManageEntity,
    KnowledgeSpaceEntity,
    KnowledgeDocumentEntity,
    DocumentChunkEntity,
    ChatFeedBackEntity,
    ConnectConfigEntity,
    ChatHistoryEntity,
    ChatHistoryMessageEntity,
]
