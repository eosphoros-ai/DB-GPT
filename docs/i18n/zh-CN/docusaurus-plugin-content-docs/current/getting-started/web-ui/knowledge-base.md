---
sidebar_position: 2
title: 知识库
---

# 知识库

构建并管理用于检索增强生成（RAG）的知识库。你可以上传文档、配置检索参数，并在对话中使用它们。

## 创建知识库

### 第一步：进入 Knowledge 页面

点击侧边栏中的 **Knowledge**，打开知识库管理页面。

### 第二步：创建新的知识库

1. 点击 **Create**（或 **+** 按钮）
2. 填写以下信息：
   - **Name**：知识库名称
   - **Description**：知识库内容简介
   - **Embedding Model**：用于向量化的 Embedding 模型（必须与当前配置一致）
3. 点击 **Create**

### 第三步：上传文档

1. 打开刚刚创建的知识库
2. 点击 **Upload** 添加文档
3. 选择一个或多个文件
4. 等待系统完成处理（分块、向量化、索引构建）

:::info 支持的文件格式
| 格式 | 扩展名 |
|---|---|
| Documents | `.pdf`, `.docx`, `.doc`, `.txt`, `.md` |
| Spreadsheets | `.xlsx`, `.xls`, `.csv` |
| Web | `.html`, `.htm` |
| Data | `.json` |
| Code | `.py`, `.java`, `.js`, `.ts` 等 |
:::

## 在对话中使用知识库

1. 进入 **Chat** 并创建新会话
2. 选择 **Chat Knowledge** 模式
3. 从下拉菜单中选择知识库
4. 开始提问，LLM 会将你的文档作为上下文使用

## 知识库设置

每个知识库都支持以下可配置项：

| 配置项 | 说明 | 默认值 |
|---|---|---|
| **Chunk Size** | 每个文本块的最大字符数 | 512 |
| **Chunk Overlap** | 相邻文本块之间的重叠长度 | 50 |
| **Top K** | 每次查询返回的文本块数量 | 5 |
| **Score Threshold** | 检索的最小相关性分数 | 0.3 |

:::tip 检索调优建议
- **文档较大**：增大 Chunk Size，以保留更多上下文
- **希望答案更全面**：提高 Top K，并适当降低分数阈值
- **结果噪声较多**：提高分数阈值
:::

## 存储类型

DB-GPT 支持多种向量存储后端：

| 后端 | 说明 | 安装 Extra |
|---|---|---|
| **ChromaDB** | 默认方案，内嵌式，无需额外部署 | `storage_chromadb` |
| **Milvus** | 面向生产环境的分布式向量数据库 | `storage_milvus` |
| **OceanBase** | 云原生分布式数据库 | `storage_oceanbase` |

如果要使用非默认后端，需要在安装命令中添加对应的 extra：

```bash
uv sync --all-packages --extra "storage_milvus" ...
```

## 高级特性

<details>
<summary><strong>Graph RAG</strong></summary>

DB-GPT 支持基于知识图谱的结构化检索：

- 从文档中抽取实体及其关系
- 在向量检索之外支持图谱检索
- 适用于概念关联复杂的领域知识场景

配置方式可参考 [Graph RAG](/docs/application/graph_rag)。

</details>

<details>
<summary><strong>关键词检索（BM25）</strong></summary>

如果需要结合向量检索与关键词检索的混合检索能力：

```bash
uv sync --all-packages --extra "rag_bm25" ...
```

这会启用 BM25 索引，并与向量检索配合使用，以提升召回效果。

</details>

## 管理知识库

| 操作 | 说明 |
|---|---|
| **View** | 点击知识库查看其中的文档和设置 |
| **Add documents** | 在知识库内使用 Upload 按钮添加文档 |
| **Delete documents** | 选中文档后点击 Delete |
| **Delete knowledge base** | 在知识库卡片上点击 Delete |

:::warning 删除操作不可恢复
删除知识库会同时移除其相关的向量数据和索引数据，原始上传文件也无法恢复。
:::

## 下一步

| 主题 | 链接 |
|---|---|
| 在对话中使用知识库 | [Chat](/docs/getting-started/web-ui/chat) |
| RAG 概念 | [RAG](/docs/getting-started/concepts/rag) |
| 高级 RAG 配置 | [RAG Tutorial](/docs/application/advanced_tutorial/rag) |
