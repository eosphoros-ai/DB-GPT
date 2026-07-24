---
id: kb_index_principles
title: 知识库文档索引原理
sidebar_label: KB Indexing Principles
---

# 知识库文档索引原理

> 讲解 DB-GPT 知识库如何对上传文档做索引——从原始文件到可被检索的索引。
> 面向产品/设计同学,不含代码,但所述机制与实现一致。

## 这里的"索引"指什么

索引发生在**文档同步时**,对话时**不再重新索引**,只做检索。
每篇文档的处理流水线是:

```
上传 ──► 加载文件 ──► 切分 ──► 向量化 ──► 写入一个或多个索引
                                  │
                                  └─► 可选地额外构建图谱
```

知识库空间通过 `index_methods`(一个字符串列表)声明要建哪种索引。三个索引**方法**可直接选择;
"结构索引"和"代码图谱"是叠加在它们之上的能力(结构索引在检索时才建;代码/标题图谱则建在
`KnowledgeGraph` 方法之上,或针对 `GIT_REPO` 空间来建)。

| 索引入口 | 代码名(`index_methods`) | 同步时建? | 能给你什么 |
|---|---|---|---|
| 向量索引 | `VectorStore` | 是 | 语义相似度排序 |
| 关键词索引 | `FullText` | 是 | 精确关键词 / BM25 命中 |
| 知识图谱索引 | `KnowledgeGraph` | 是 | 对实体/标题/代码做图遍历 |
| 结构索引 | *(检索时建树)* | 否,查询时重建 | Markdown 标题树 / 父子导航 |
| 代码图谱 | *(叠加在 `KnowledgeGraph` / `GIT_REPO`)* | 是 | 代码文件的 AST,产出 `function`/`class` 节点 |

> 一句话:**向量、关键词、知识图谱**是三种持久化索引方法。**结构索引**和**代码图谱**是 DB-GPT 在它们之上
> 构建的两种额外索引形态。

---

## 1. 结构索引——按文档结构导航

### 是什么
一种对"已切好分"文档的*视图*:按 Markdown 标题层级(H1→H2→H3…)把所有 chunk 组织成一棵树。每个 chunk
在切分阶段就已经带了 `Header1/Header2/…` 元数据(见下方*元数据链路*);结构索引只是把这些 chunk
*组织*成树,让检索能向上跳到父章节、再向下展开它的子节点——而不是把每个 chunk 当成孤立的小岛。

### 为什么单列(尽管它没有自己的索引方法)
索引阶段 DB-GPT **持久化**的是每个 chunk 上的标题路径,**并不**持久化这棵树。**检索时**检索器才根据
这些 `HeaderN` 字段在内存里重建树并遍历(“找到这个叶子 chunk,然后展开它整个父章节,再排序”)。所以
"结构索引"本质是*结构化元数据 + 树视图检索器*,不是独立的存储。

### 原理(怎么建、怎么用)
```
markdown 文档               切分时每个 chunk 写入 HeaderN
──────────────              ──────────────────────────────────
# 提示词缓存设计       ──►  chunk A  { H1: "提示词缓存设计" }
   ## 核心原理         ──►  chunk B  { H1: "提示词缓存", H2: "核心原理" }
      ### 命中条件      ──►  chunk C  { H1..H3: "命中条件" }
   ## 三种策略对比     ──►  chunk D  { H1: "提示词缓存", H2: "三种策略对比" }
                                     │
                       检索时按 H1>H2>H3 组织成树
                                     ▼
                            ┌── H1 提示词缓存 ──┐
                            │                   │
                       H2 核心原理         H2 三种策略对比
                            │                   │
                       H3 命中条件         (chunk D)
                       (chunk C)
```

- 最擅长:"这一整章讲了啥?""总结第三章"、父节点的上下文扩展。
- 注意:非 Markdown 文档没有标题层级,结构树退化为一个扁平列表——它的价值主要集中在 Markdown / 结构化文档上。

---

## 2. 知识图谱索引——关系型检索

这是最丰富的索引,而且它内部**不是一张图,而是好几张图**,在启用 `KnowledgeGraph` 方法时一起建:

```
启用 index_methods = KnowledgeGraph
        │
        ├── (a) LLM 三元组抽取图     语义图:  (实体) -谓词- (实体)
        ├── (b) 文档-段落结构图      结构图:  document → chunk → chunk (include / next)
        ├── (c) Markdown 标题层级图  结构图:  file → H1 → H2 → H3 (contains)
        └── (d) 代码图谱             结构图:  repository → file → function/class (defines)
```

(a) 和 (b) 落在**知识图谱存储**(TuGraph / Neo4j / Memgraph);(c) 和 (d) 都落在**代码图谱表**,共用同一个 builder。

### 2a. LLM 三元组抽取图(语义图)
把每个 chunk 喂给 LLM,用抽取提示词让它返回 `(主语, 谓词, 宾语)` 三元组,再 upsert 进图存储,变成
`实体 -边- 实体`。这就是经典的"从文本里抽知识图谱":它抓住纯关键词/向量检索抓不到的**事实和关系**。

```
chunk 文本: "Anthropic 的 prompt cache 通过复用 KV 矩阵来降低成本"
      │  LLM 三元组抽取提示词
      ▼
(Anthropic) ──has──▶ (Prompt Cache)
(Prompt Cache) ──reuses──▶ (KV 矩阵)
(Prompt Cache) ──cuts──▶ (成本)
```
检索时沿边遍历:命中一个实体就连带展开它的邻居,而每条边记得自己来自哪个 chunk(边上有 `_chunk_id`
属性),所以答案照样能溯源回原文。

### 2b. 文档-段落结构图
独立于三元组,KG 存储还会建一个结构骨架:`document -include- chunk`、`chunk -include- chunk`
(chunk 嵌套时的父子)、`chunk -next- chunk`(阅读顺序)。这让检索能从实体 → 包含它的 chunk → 文档
→ 相邻 chunk 一路跳转。(若启用社区汇总变体,还会跑社区检测并用 LLM 总结每个社区。)

### 2c. Markdown 标题层级图
对 `KnowledgeGraph` 方法空间下的 `.md` 文件,builder 从已存的 chunk 重建文件全文,扫描
`^(#{1,6})\s+` 标题行(跳过代码块里的标题),产出 `heading` 节点和 `contains` 边:
`file → H1 → H2 → H3`。这相当于上面结构索引的图版本——区别是用边的遍历来查,而不是内存里的树。

### 2d. 代码图谱
这一节最值得理解。构建 Markdown 标题图的**同一个** `RepoGraphBuilder`,还能从**源代码**构建图谱,它
正是 `GIT_REPO` 空间(或上传到 `KnowledgeGraph` 方法空间的代码文件)做代码级检索的根基。

**原理——用 AST 解析,不是用正则:**

```
遍历仓库
  repository  ──contains──▶  file
                              │ 扩展名推断语言
   ┌──────────────────────────┼───────────────────────────┐
   │                          │                            │
 .py/.java/.js/.ts/       .md/.markdown              其他语言
 .go/.rs/.c/.cpp          (标题图 2c)                (正则兜底)
   │                                                     │
   ▼ 用 tree-sitter 解析                                  ▼ 正则扫 def/class
 function_definition / class_definition / ...        file ──defines──▶ function|class
   │
   ▼ 每个目标 AST 节点
 创建节点: type=function|class|method|class|interface|impl|struct|enum|trait
          name, file_path, start_line, end_line, language
 加边:   file ──defines──▶ <该节点>
```

- **节点**: `repository`、`file`,以及代码节点 `function` / `class` / `method` / `interface` /
  `impl` / `struct` / `enum` / `trait`。
- **builder 产出的边**: `contains`(repo→file、file→heading)和 `defines`(file→代码节点)。
- **解析器**: 对 **tree-sitter** 支持 Python / Java / JavaScript / TypeScript / Go / Rust / C / C++。
每种目标 AST 节点类型(如 `function_definition`、`class_definition`、`method_declaration`、
`interface_declaration`、`struct_item`)会被映射成语义节点类型。没有 tree-sitter 语法的语言退回
正则 `def`/`class` 扫描,仍会产出 `file -defines-> function|class` 边。
- **能干嘛**: "`apply_anthropic_cache_control` 定义在哪?""列出 `PromptCache` 类的所有方法"——靠节点
查询 + `defines` 边遍历命中,而不是靠模糊的向量近似。

> **关于边,要诚实交代。** 检索层还支持 `CALLS` / `INHERITS` / `IMPLEMENTS` / `IMPORTS` / `REFERENCES`
> 边(用于调用链、类继承查询)。但当前的 `RepoGraphBuilder` **只产出** `contains` 和 `defines`。
> 因此调用链/继承遍历只有在别的 builder 产出过这些边时才会有结果;纯由本 builder 构建的图上它们会是空的。
> 设计依赖调用图的功能时务必注意这一点。

---

## 3. 向量索引——语义相似度

```
chunk ──embedding 模型──► [0.12, -0.34, 0.56, …] (如 1024 维) ──► 向量库
问题  ──embedding 模型──► 问题向量 ──余弦相似度──► Top-K chunks
```

### 原理
每个 chunk 过一遍 embedding 模型,把文本映射成高维向量;向量 + chunk 元数据一起批量 upsert 进向量库
(Chroma / Milvus / PGVector / Qdrant / Weaviate / …,由空间配置决定)。检索时把问题同样 embedding,
向量库返回与问题向量最近(余弦/内积)的 chunk。

### 为什么是默认项
向量检索能抓*改写/同义*:"缓存机制"也能命中"prompt cache",因为即使没有共词,向量也挨得近。它不需要
任何文档结构信息,所有文件类型通吃。

### 弱点
一个向量是把整段 chunk 平均成一个点——如果 chunk 混了两个主题就会糊;如果精确词很重要(API 名、错误
码)就可能漏掉。所以关键词索引 + 向量索引通常一起开。

---

## 4. 关键词索引——精确词匹配(BM25)

```
chunk ──作为文本写入搜索引擎──► BM25 词项索引
问题  ──分词──► "词项" ──对 chunk 算 BM25 分──► Top-K chunks
```

### 原理
chunk 原样作为文本文档存进全文搜索引擎(Elasticsearch,用 BM25 打分;`k1`/`b` 可调)。检索时对问题做
分词,按 BM25 分返回 chunk——即按"词频 × 逆文档频率 + 长度归一"打分。没有 embedding、没有 LLM,纯词法匹配。

### 什么时候赢
精确标识符:`apply_anthropic_cache_control`、`ERR_CONN_REFUSED`、某个配置 key。向量检索可能把这种精确词
稀释成"相似但错误"的邻居;BM25 则精确命中并排到最前。

### 弱点
抓不到同义词/改写(分词后"caching"不一定能稳稳命中"cache",更别提"缓存")。它纯粹是向量索引的补充。

---

## 四种索引在检索时如何协同

```
                      用户问题
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
    向量           关键词 (BM25)        知识图谱
   语义命中         精确命中          / 结构 / 代码
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                  融合 + 重排(结构树可在此展开父节点)
                          │
                          ▼
                  Top-K chunks ──► 拼进 LLM Prompt ──► 带引用的回答
```

---

## 切分与元数据链路(四种索引的共同地基)

四种索引都作用在*同一批 chunk* 上,所以切分质量决定检索质量。

**切分策略**
- Markdown 标题切分(`H1→H2→H3`):保留语义边界 + 标题路径,最适合技术文档。
- 按大小切分(固定字符数):适合没有结构的纯文本。
- 按分隔符切分(段落 / 换行 / 表格单元格):适合表格 / 非结构化内容。

**索引时写入每个 chunk 的元数据**(后续所有索引和引用溯源都靠它):

```
上传                  切分                        存储
──────                ──────                      ─────
file_name: prompt.md → chunk_id: 101            → vector: [0.12, ...]
file_path: /docs/...  → doc_name: prompt.md     → content: "前缀逐字..."
doc_type: DOCUMENT    → chunk_type: text        → meta_info: {
index_methods:        → file_path: /docs/...    →   "Header1": "提示词缓存",
 [Vector, FullText,   → header_path: H1>H2>H3   →   "Header2": "核心原理",
  KG]                                             →   "Header3": "命中条件"
                                                  → }
```

---

## 关键设计原则

1. **三种持久化索引方法**——`VectorStore`、`FullText`、`KnowledgeGraph`——空间级可任意组合。
2. **结构索引是"元数据 + 检索时建树"**,不是独立存储;它依赖切分时写入的 `HeaderN`。
3. **知识图谱索引是一组图**——LLM 三元组、文档-段落骨架、Markdown 标题、代码图谱(AST)——共用一套构建链路。
4. **代码图谱用 tree-sitter 解析**,产出 `function`/`class` 节点 + `defines` 边,是代码级问答精准命中的
   根基。注意调用/继承边当前 builder 并不填充。
5. **一次切分,四索引共用**——chunk 质量和 `HeaderN` 元数据是所有索引的地基;按文档类型切分
   (Markdown→标题、文本→大小、表格→分隔符)。
6. **索引/对话解耦**——索引在同步时完成,对话只检索,不重新索引。