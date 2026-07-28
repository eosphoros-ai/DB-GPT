# Graph RAG

Graph RAG 是用 DB-GPT **知识图谱索引**的检索模式。在知识空间上启用 `KnowledgeGraph` 索引方法后,DB-GPT 会构建*一组图*,通过图遍历来检索(可替代或补充向量 / 关键词检索)。

## 会构建哪些图

| 图 | 适用 | 捕获内容 |
|---|---|---|
| **LLM 三元组图** | 任意文本 | `(主语, 谓词, 宾语)` 事实与关系 |
| **文档-段落图** | 任意文档 | `document → chunk → chunk` 结构(`include`/`next`) |
| **Markdown 标题图** | `.md` 文件 | `file → H1 → H2 → H3` 标题层级(`contains`) |
| **代码图谱** | 代码文件 / `GIT_REPO` 空间 | 用 **tree-sitter** 解析的代码 AST → `function`/`class`/`method` 节点 + `file → defines` 边 |

四者共用一条构建链路,写入配置的图存储(TuGraph / Neo4j / Memgraph)。

## 检索原理

`GraphRetriever` 按关键词、按节点 embedding 向量、按自然语言转图查询(Text2GQL)、以及按文档-图关联来匹配图节点,再沿边展开。每条边记得来自哪个 chunk,所以答案仍可溯源。

:::note
retriever 能遍历 `CALLS`/`INHERITS`/`IMPLEMENTS` 边,但当前代码图谱 builder **只产出** `contains` 和 `defines`。调用链/继承查询除非别的 builder 产出过这些边,否则为空。
:::

## 更多

- [知识库索引原理](/docs/design/kb_index_principles)——图谱族与代码图谱 AST 解析的深入讲解
- [Agentic RAG 对话原理](/docs/design/agentic_rag_principles)——图检索如何融入 agentic 循环
- [Graph RAG Cookbook](/docs/cookbook/rag/graph_rag_app_develop)——编程构建 Graph RAG 应用
- [TuGraph 集成](/docs/installation/integrations/graph_rag_install)——安装图存储后端