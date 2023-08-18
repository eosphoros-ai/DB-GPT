.. DB-GPT documentation master file, created by
   sphinx-quickstart on Wed May 24 11:50:49 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to DB-GPT!
==================================
| As large models are released and iterated upon, they are becoming increasingly intelligent. However, in the process of using large models, we face significant challenges in data security and privacy. We need to ensure that our sensitive data and environments remain completely controlled and avoid any data privacy leaks or security risks. Based on this, we have launched the DB-GPT project to build a complete private large model solution for all database-based scenarios. This solution supports local deployment, allowing it to be applied not only in independent private environments but also to be independently deployed and isolated according to business modules, ensuring that the ability of large models is absolutely private, secure, and controllable.

| **DB-GPT** is an experimental open-source project that uses localized GPT large models to interact with your data and environment. With this solution, you can be assured that there is no risk of data leakage, and your data is 100% private and secure.

| **Features**
Currently, we have released multiple key features, which are listed below to demonstrate our current capabilities:

- SQL language capabilities
  - SQL generation
  - SQL diagnosis

- Private domain Q&A and data processing
  - Database knowledge Q&A
  - Data processing

- Plugins
  - Support custom plugin execution tasks and natively support the Auto-GPT plugin, such as:

- Unified vector storage/indexing of knowledge base
  - Support for unstructured data such as PDF, Markdown, CSV, and WebURL

- Milti LLMs Support
  - Supports multiple large language models, currently supporting Vicuna (7b, 13b), ChatGLM-6b (int4, int8)
  - TODO: codegen2, codet5p

Getting Started
-----------------
| How to get started using DB-GPT to interact with your data and environment.
- `Quickstart Guide <./getting_started/getting_started.html>`_

| Concepts and terminology

- `Concepts and Terminology  <./getting_started/concepts.html>`_

| Coming soon...

- `Tutorials <.getting_started/tutorials.html>`_
.. toctree::
   :maxdepth: 2
   :caption: Getting Started
   :hidden:

   getting_started/install.rst
   getting_started/application.md
   getting_started/installation.md
   getting_started/concepts.md
   getting_started/tutorials.md
   getting_started/faq.rst


Modules
---------

| These modules are the core abstractions with which we can interact with data and environment smoothly.
It's very important for DB-GPT, DB-GPT also provide standard, extendable interfaces.

| The docs for each module contain quickstart examples, how to guides, reference docs, and conceptual guides.

| The modules are as follows

- `LLMs <./modules/llms.html>`_: Supported multi models management and integrations.

- `Prompts <./modules/prompts.html>`_: Prompt management, optimization, and serialization for multi database.

- `Plugins <./modules/plugins.html>`_: Plugins management, scheduler.

- `Knowledge <./modules/knowledge.html>`_: Knowledge management, embedding, and search.

- `Connections <./modules/connections.html>`_: Supported multi databases connection. management connections and interact with this.

- `Vector <./modules/vector.html>`_: Supported multi vector database.

.. toctree::
   :maxdepth: 2
   :caption: Modules
   :name: modules
   :hidden:

   ./modules/llms.md
   ./modules/prompts.md
   ./modules/plugins.md
   ./modules/connections.rst
   ./modules/knowledge.rst
   ./modules/vector.rst

Use Cases
---------

| Best Practices and built-in implementations for common DB-GPT use cases:

- `Sql generation and diagnosis <./use_cases/sql_generation_and_diagnosis.html>`_: SQL generation and diagnosis.

- `knownledge Based QA <./use_cases/knownledge_based_qa.html>`_: A important scene for user to chat with database documents, codes, bugs and schemas.

- `Chatbots <./use_cases/chatbots.html>`_: Language model love to chat, use multi models to chat.

- `Querying Database Data <./use_cases/query_database_data.html>`_: Query and Analysis data from databases and give charts.

- `Interacting with apis <./use_cases/interacting_with_api.html>`_: Interact with apis, such as create a table, deploy a database cluster, create a database and so on.

- `Tool use with plugins <./use_cases/tool_use_with_plugin>`_: According to Plugin use tools to manage databases autonomoly.

.. toctree::
   :maxdepth: 2
   :caption: Use Cases
   :name: use_cases
   :hidden:

   ./use_cases/sql_generation_and_diagnosis.md
   ./use_cases/knownledge_based_qa.md
   ./use_cases/chatbots.md
   ./use_cases/query_database_data.md
   ./use_cases/interacting_with_api.md
   ./use_cases/tool_use_with_plugin.md

Reference
-----------
| Full documentation on all methods, classes, installation methods, and integration setups for DB-GPT.

.. toctree::
   :maxdepth: 1
   :caption: Reference
   :name: reference
   :hidden:

   ./reference.md


Resources
----------

| Additional resources we think may be useful as you develop your application!

- `Discord <https://discord.gg/eZHE94MN>`_: if your have some problem or ideas, you can talk from discord.

.. toctree::
   :maxdepth: 1
   :caption: Resources
   :name: resources
   :hidden:
