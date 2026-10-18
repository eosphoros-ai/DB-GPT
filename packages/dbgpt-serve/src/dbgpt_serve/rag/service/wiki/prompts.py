"""Wiki generation prompt templates.

Ported from WeKnora's ``internal/agent/prompts_wiki.go`` contract, tuned
for DB-GPT. Shared invariants across all prompts:

- Wiki links use the ``[[slug|display]]`` syntax.
- Pages start their output with a ``SUMMARY:`` line (single sentence).
- JSON output is expected unless stated otherwise.
"""

WIKI_GRANULARITY_GUIDANCE = {
    "focused": (
        "只提取最核心的实体与概念（当前批次每个文档最多 2~3 个候选页面），"
        "宁缺毋滥。适合快速构建高信噪比的 Wiki。"
    ),
    "standard": (
        "提取主要实体、概念与机制（当前批次每个文档 3~8 个候选页面），"
        "覆盖要点与高频引用对象。"
    ),
    "exhaustive": (
        "尽可能完整地提取实体、概念、流程、机制与对比关系"
        "（当前批次每个文档最多 16 个候选页面），适合高价值语料。"
    ),
}

WIKI_CANDIDATE_SLUG_PROMPT = """你是知识库 Wiki 架构师。从下面的文档内容中抽取应当沉淀为 Wiki 页面的知识条目（实体、概念、机制）。

## 要求
1. {granularity}
2. {extraction_instructions}
3. 每个 条目 输出: name（中文名）、slug（拼音或英文小写连字符，前缀标识类型: entity/ 或 concept/）、aliases（含 name 在内的所有别名列表）、description（一句话描述，用于合并判重）
4. slug 命名稳定：同类事物跨文档必须使用相同 slug，便于页面聚合
5. 已存在的 Wiki 页面（下方给出）应当复用其 slug，而不是另起新页
6. 不要为整个文档本身创建页面，文档摘要由系统另行处理

## 已存在页面（slug 列表）
{existing_slugs}

## 文档内容
<document title="{doc_name}">
{content}
</document>

以 JSON 输出，不要输出其他内容：
{{
  "candidates": [
    {{"name": "…", "slug": "entity/…或concept/…", "aliases": ["…"], "description": "…"}}
  ]
}}"""

WIKI_DOC_SUMMARY_PROMPT = """为以下文档生成一页 Wiki 摘要页。

## 要求
1. 第一行输出 `SUMMARY: <一句话摘要>`（不带任何 markdown）
2. 正文用 Markdown，简要概括文档的结构与关键信息（表格/列表优先）
3. 正文中提及其他知识实体时使用 [[entity/slug|别名]] 或 [[concept/slug|别名]] 链接，只能使用下方给出的候选 slug
4. 长度 200~500 字，不要逐字复制原文

## 候选页面（可链接）
{candidate_links}

## 文档
<document title="{doc_name}">
{content}
</document>"""

WIKI_CHUNK_CITATION_PROMPT = """你是知识引用标注器。将「候选知识条目」映射到支持它们的「分块证据」。

## 要求
1. 对每个条目，从给定分块中找出支持其内容的最相关分块编号（chunk_id 取给出的分块标识）
2. 条目在分块中没有证据支撑时，不要强行引用，留空数组
3. 若某条目描述的对象其实是一个新的、值得单独成页的知识点，可加入 new_slugs（格式同候选条目）
4. 只输出 JSON

## 候选条目
{candidates_json}

## 分块（每块开头为其标识）
{chunks_text}

输出：
{{
  "citations": [
    {{"slug": "entity/…", "chunk_ids": ["c3", "c1"]}}
  ],
  "new_slugs": [ {{"name": "…", "slug": "entity/…", "aliases": ["…"], "description": "…"}} ]
}}"""

WIKI_DEDUP_PROMPT = """对下列候选知识条目做合并判重。items 中 group 相同的条目是表面相似（疑似同一对象）的分组，请逐组判断。

## 要求
1. 仅当条目描述的是**同一对象**（同一个人/系统/流程/机制/产品）时才合并，名称相近但对象不同的不要合并
2. 判定为同一对象时，输出一条合并后的条目，保留信息更完整的 name / slug（优先沿用已存在页面的 slug 与别名），aliases 取并集、description 融合为一句，并在 merged_from_slugs 中列出被合并条目的全部原 slug
3. 判定为不同对象的，原样保留输出
4. 其他未分组条目原样返回；只输出 JSON

## 条目
{candidates_json}

输出：
{{
  "candidates": [
    {{"name": "…", "slug": "…", "aliases": ["…"], "description": "…", "merged_from_slugs": ["…"]}}
  ]
}}"""

WIKI_TAXONOMY_PROMPT = """为知识库 Wiki 设计目录结构（最多两级）。

## 要求
1. 结合已有目录（尽量复用，保持稳定），把条目归入目录；新目录仅在明显需要时创建
2. 目录名用中文短词；一级目录≤8 个，每个一级目录下二级目录≤6 个
3. 无法归类的条目放在根目录（目录为空数组）

## 已有目录结构
{existing_tree}

## 条目（请为每一条给出目录路径 category_path）
{candidates_json}

输出：
{{
  "assignments": [
    {{"slug": "entity/…", "category_path": ["一级目录", "二级目录"]}}
  ],
  "new_folders": [["一级目录", "二级目录"]]
}}"""

WIKI_PAGE_MODIFY_PROMPT = """你是 Wiki 编辑整理器（编译器，而不是作者）。基于新材料更新一个 Wiki 页面。

## 铁律
1. 只写有材料支撑的内容，禁止编造、扩展与想象
2. 与页面主题无关的内容丢弃（本页主题见 <page>）
3. 新信息与已有内容冲突且无法判断时，以更新时间较新的材料为准，其余放入「争议」段
4. 链接语法 [[slug|别名]]；正文出现其他页面主题词时尽量建立链接，但只能使用 valid_wiki_links 中给出的 slug
5. 在 <deleted_documents> 里出现的文档已被撤稿：删除其中信息在正文中的所有痕迹
6. 不要重复、不要堆砌；保持条理：概述 → 分节展开；表格与列表优先
7. 第一行输出 `SUMMARY: <一句话摘要>`；第二行空行后输出 Markdown 正文

## 页面
<page slug="{slug}" type="{page_type}">
{existing_content}
</page>

## valid_wiki_links（可用于链接的 slug）
{valid_links}

## 新材料
{materials}

## 撤稿文档
<deleted_documents>
{deleted_documents}
</deleted_documents>

## 风格要求
{content_instructions}"""

WIKI_INDEX_INTRO_PROMPT = """为知识库 Wiki 生成首页（索引页）。

## 要求
1. 第一行输出 `SUMMARY: <这个知识库的一句话定位>`
2. 正文用 Markdown 按目录分组导航（引用下方给出的页面，使用 [[slug|标题]] 链接，并附每页一句话简介）
3. 篇幅精炼，作为全库入口；不收录未列出的页面

## 目录与页面
{tree_markdown}

直接输出（不要 JSON）。"""

WIKI_INDEX_INTRO_UPDATE_PROMPT = """更新知识库 Wiki 首页（索引页）。

## 要求
1. 第一行输出 `SUMMARY: <一句话定位>`
2. 在既有首页基础上只做增量调整：新增页面补入对应目录分组；已删除页面移除；分组结构保持稳定
3. 使用 [[slug|标题]] 链接，并附每页一句话简介

## 既有首页
{existing_intro}

## 目录与页面
{tree_markdown}

直接输出（不要 JSON）。"""
