---
sidebar_position: 3
title: AWEL Flow
---

# AWEL Flow

使用 AWEL Flow 编辑器以可视化方式构建 AI 工作流。它提供拖拽式界面，无需编写代码即可组合 LLM 流水线。

## 什么是 AWEL Flow？

AWEL Flow 是 **AWEL（Agentic Workflow Expression Language）** 的可视化编辑器。你可以通过它：

- 将算子拖放到画布上
- 将它们连接成 DAG（有向无环图）
- 配置每个算子的参数
- 测试并部署工作流

:::info 代码方式与可视化方式
AWEL 工作流既可以通过 Python 代码编写，也可以在 Flow 编辑器中可视化搭建。Flow 编辑器生成的是相同的底层 DAG 结构。
:::

## 快速开始

### 第一步：打开 Flow 编辑器

1. 在侧边栏进入 **Flow**
2. 点击 **Create** 新建工作流

### 第二步：添加算子

左侧面板会按类别显示可用算子：

| 类别 | 示例 |
|---|---|
| **Trigger** | HTTP Trigger、Schedule Trigger |
| **LLM** | LLM Operator、Streaming LLM |
| **RAG** | Knowledge Retriever、Reranker |
| **Agent** | Agent Operator、Planning |
| **Data** | Database Query、File Reader |
| **Transform** | Text Splitter、JSON Parser |
| **Output** | Response、Stream Response |

将算子从面板拖到画布上即可。

### 第三步：连接算子

从一个算子的输出端口点击并拖动到另一个算子的输入端口，即可创建连接。数据会沿着这些连接流动。

### 第四步：配置算子

点击任意算子即可打开配置面板。你可以设置如下参数：

- 模型名称
- Prompt 模板
- 数据库连接
- Chunk 大小
- 自定义逻辑

### 第五步：测试并保存

1. 点击 **Run**，使用示例输入测试工作流
2. 查看每个阶段的输出结果
3. 点击 **Save** 保存工作流

## 示例：简单的 RAG 工作流

一个基础 RAG 工作流通常会连接以下算子：

```mermaid
graph LR
  T[HTTP Trigger] --> R[Knowledge Retriever]
  R --> P[Prompt Builder]
  P --> L[LLM Operator]
  L --> O[Stream Response]
```

1. **HTTP Trigger**：接收用户问题
2. **Knowledge Retriever**：在知识库中检索相关内容块
3. **Prompt Builder**：将问题与检索到的上下文组合起来
4. **LLM Operator**：生成答案
5. **Stream Response**：返回流式响应

## 在应用中使用 Flow

创建好的工作流可以作为应用的后端执行引擎：

1. 在 Flow 编辑器中保存工作流
2. 进入 **Apps** → **Create**
3. 选择已保存的 Flow 作为应用的执行引擎
4. 应用会继承该 Flow 的输入和输出定义

## 管理 Flow

| 操作 | 说明 |
|---|---|
| **Edit** | 打开某个 Flow 并修改算子或连接 |
| **Duplicate** | 复制一个现有 Flow |
| **Export** | 将 Flow 定义下载为 JSON |
| **Import** | 上传 Flow 定义 JSON 文件 |
| **Delete** | 从列表中删除 Flow |

## 安装社区算子

来自 [dbgpts repository](https://github.com/eosphoros-ai/dbgpts) 的社区算子在安装后会自动出现在 Flow 编辑器中：

```bash
dbgpts install <operator-package>
```

## 下一步

| 主题 | 链接 |
|---|---|
| AWEL 概念 | [AWEL](/docs/getting-started/concepts/awel) |
| AWEL Python 教程 | [AWEL Tutorial](/docs/awel/tutorial) |
| AWEL Cookbook | [AWEL Cookbook](/docs/awel/cookbook) |
| 社区算子 | [dbgpts](/docs/getting-started/tools/dbgpts) |
