---
sidebar_position: 4
title: LLM-Wiki
---

# Organize knowledge with LLM-Wiki

LLM-Wiki adds a reading layer to a knowledge space. It uses a language model to organize document content into summaries, concept or entity pages, and links between them. Use it when readers need to understand a collection's structure before searching for a specific passage.

For metric governance, a Wiki can bring together the definition of net receipts, refund attribution, and related terms. These pages are generated interpretations. The source documents remain the authority.

## Enable Wiki generation

When creating a [knowledge space](/docs/getting-started/web-ui/knowledge-base), select **LLM-Wiki Index** under **Index Method**.

![Creation form with the optional LLM-Wiki index](/img/data-agent/en/knowledge-create.png)

The screenshot shows the option before it is selected. Enable it for the space where you want Wiki generation. Review the Wiki settings offered by the form:

| Setting | Use it to |
|---|---|
| Extraction granularity | Choose a focused collection or more detailed page coverage |
| Generation model | Select an available model for generation |
| Maximum new pages | Limit how many new pages a batch may introduce |
| Content instructions | Guide the organization, such as “group by business concept and preserve source references” |

Check model access before importing a large collection. Wiki generation adds model calls beyond document processing; an enabled option does not guarantee a successful generation job.

## Generate and inspect

Upload or synchronize documents and confirm their processing state. In a Wiki-enabled space, source processing can enqueue incremental Wiki generation. Open **Wiki** to inspect its results; use **Generate / Rebuild** when you need to generate or rebuild the collection.

![Wiki tab before any pages have been generated](/img/data-agent/en/knowledge-wiki.png)

This is the English UI of an empty Wiki. Zero pages means there is no generated collection to read yet. The presence of the tab or a document's `FINISHED` state is not proof that Wiki generation succeeded.

Before retrying an empty or failed Wiki, check the source documents, the selected model, generation errors, and server logs. A quota or permission error requires fixing model access.

## Read and review pages

Once generation succeeds, use the catalog and search to find a page. The **Knowledge** and **Summaries** views help distinguish organized topics from document summaries. Review a page's source references and backlinks, then follow related page links.

Use **Wiki Graph** to explore links between generated pages. This is separate from Markdown/code graph processing and does not certify relationships in a live database.

For each important page, check:

1. Its definition agrees with the source passages.
2. Exceptions and date/version qualifications are preserved.
3. Related pages do not introduce conflicting rules.
4. References point to the intended source material.

For missing or incorrect content, inspect the source first. Use the page's editing and history controls where available; review the recorded versions when comparing or reverting changes. Regeneration can introduce new interpretations, so inspect important pages again afterward.

## Use Wiki in an agent task

Select the Wiki-enabled knowledge space for the task. An agent with Wiki tools can browse the catalog, search pages, and read a selected page through `kb_wiki_index`, `kb_wiki_search`, and `kb_wiki_read_page`. Tool availability depends on the selected space and execution context.

Try: “Map the concepts related to net receipts in this knowledge base, then cite the source rules for refund attribution.” Inspect both the generated page and the original document references. Page-writing tools are available only in supported contexts; selecting a knowledge space alone is not a guarantee of edit access.

For questions requiring precise source support, continue with [Knowledge Base Chat](/docs/application/apps/chat_knowledge). For updated external material, inspect [source synchronization](/docs/getting-started/web-ui/external-datasources) before rebuilding the Wiki.
