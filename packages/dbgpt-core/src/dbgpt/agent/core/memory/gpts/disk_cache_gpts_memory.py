import logging
from concurrent.futures import Executor
from typing import List, Optional

from diskcache import FanoutCache

from dbgpt.agent import GptsMemory
from dbgpt.agent.core.memory.gpts import GptsMessage, GptsMessageMemory, GptsPlansMemory

logger = logging.getLogger(__name__)


class DiskCacheGptsMemory(GptsMemory):
    def __init__(
        self,
        plans_memory: Optional[GptsPlansMemory] = None,
        message_memory: Optional[GptsMessageMemory] = None,
        executor: Optional[Executor] = None,
    ):
        """Create a memory to store plans and messages."""
        super().__init__(plans_memory, message_memory, executor)
        self.messages_cache_new = FanoutCache(
            "./pilot/message/cache-dir",
            shards=4,  # 根据CPU核心数设置分片
            size_limit=4 * 1024**3,  # 3GB 总大小限制
            cull_limit=50,  # 当缓存满时删除50个旧条目
            disk_min_file_size=1024,  # ≤1KB存SQLite，>1KB存文件
            # 性能调优
            timeout=0.3,  # 锁等待超时300ms
            sqlite_journal_mode="MEM",  # 内存日志模式（风险与性能取舍）
            sqlite_mmap_size=2**26,  # 64MB内存映射加速
            compress_level=0,  # 关闭压缩
            # 存储策略优化
            disk_pickle_protocol=4,  # 使用最高效的序列化协议
        )
        self.messages_cache_new.clear()

    def _cache_messages(self, conv_id: str, messages: List[GptsMessage]):
        """缓存消息到内存或磁盘"""
        messages_cache = self.messages_cache_new.get(conv_id)
        if not messages_cache:
            messages_cache = {}
        for message in messages:
            # 确保消息ID在缓存列表中
            if message.message_id not in self.messages_id_cache[conv_id]:
                self.messages_id_cache[conv_id].append(message.message_id)
            # 存储消息内容
            messages_cache[message.message_id] = message.to_dict()

        self.messages_cache_new.set(conv_id, messages_cache)

    async def get_messages(self, conv_id: str) -> List[GptsMessage]:
        """获取会话消息（支持磁盘缓存）"""
        if conv_id not in self.messages_id_cache:
            await self.load_persistent_memory(conv_id)

        messages = []

        messages_cache = self.messages_cache_new.get(conv_id)
        if not messages_cache:
            logger.error("对话:{conv_id} not get message in cache!")
            return []
        for msg_id in self.messages_id_cache[conv_id]:
            msg_dict = messages_cache[msg_id]
            if msg_dict:
                messages.append(GptsMessage.from_dict(msg_dict))  # 反序列化
            else:
                logger.error("MsgId:{msg_id} not get message info in cache!")

        return messages
