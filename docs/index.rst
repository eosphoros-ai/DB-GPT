.. DB-GPT documentation master file, created by
   sphinx-quickstart on Wed May 24 11:50:49 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Overview
------------------

| DB-GPT is an open-source framework for large models in the databases fields. It's purpose is to build infrastructure for the domain of large models, making it easier and more convenient to develop applications around databases. By developing various technical capabilities such as:

1. **SMMF(Service-oriented Multi-model Management Framework)**
2. **Text2SQL Fine-tuning**
3. **RAG(Retrieval Augmented Generation) framework and optimization**
4. **Data-Driven Agents framework collaboration**
5. **GBI(Generative Business intelligence)**

etc, DB-GPT simplifies the construction of large model applications based on databases. 

| In the era of Data 3.0, enterprises and developers can build their own customized applications with less code, leveraging models and databases.

Features
^^^^^^^^^^^

| **1. Private Domain Q&A & Data Processing**
| Supports custom construction of knowledge bases through methods such as built-in, multi-file format uploads, and plugin-based web scraping. Enables unified vector storage and retrieval of massive structured and unstructured data.

| **2.Multi-Data Source & GBI(Generative Business intelligence)**
| Supports interaction between natural language and various data sources such as Excel, databases, and data warehouses. Also supports analysis reporting. 

| **3.SMMF(Service-oriented Multi-model Management Framework)**
| Supports a wide range of models, including dozens of large language models such as open-source models and API proxies. Examples include LLaMA/LLaMA2, Baichuan, ChatGLM, Wenxin, Tongyi, Zhipu, Xinghuo, etc.

| **4.Automated Fine-tuning**
| A lightweight framework for automated fine-tuning built around large language models, Text2SQL datasets, and methods like LoRA/QLoRA/Pturning. Makes TextSQL fine-tuning as convenient as a production line.

| **5.Data-Driven Multi-Agents & Plugins**
| Supports executing tasks through custom plugins and natively supports the Auto-GPT plugin model. Agents protocol follows the Agent Protocol standard.

| **6.Privacy and Security**
| Ensures data privacy and security through techniques such as privatizing large models and proxy de-identification.


Getting Started
^^^^^^^^^^^^^^^^^

| Quickstart 

- `Quickstart Guide <./getting_started/getting_started.html>`_ 

| Concepts and terminology

- `Concepts and Terminology  <./getting_started/concepts.html>`_

.. toctree::
   :maxdepth: 2
   :caption: Getting Started
   :name: getting_started
   :hidden:

   getting_started/install.rst
   getting_started/application.md
   getting_started/installation.md
   getting_started/concepts.md
   getting_started/tutorials.md
   getting_started/faq.rst
   getting_started/observability.md


Modules
^^^^^^^^^

| These modules are the core abstractions with which we can interact with data and environment smoothly. It's very important for DB-GPT, DB-GPT also provide standard, extendable interfaces.

| The docs for each module contain quickstart examples, how to guides, reference docs, and conceptual guides.

| The modules are as follows

- `LLMs <./modules/llms.html>`_: Supported multi models management and integrations.

- `Prompts <./modules/prompts.html>`_: Prompt management, optimization, and serialization for multi database.

- `Plugins <./modules/plugins.html>`_: Plugins management, scheduler.

- `Knowledge <./modules/knowledge.html>`_: Knowledge management, embedding, and search.

- `Connections <./modules/connections.html>`_: Supported multi databases connection. management connections and interact with this.

- `Vector <./modules/vector.html>`_: Supported multi vector database.

-------------

.. toctree::
   :maxdepth: 2
   :caption: Modules
   :name: modules
   :hidden:

   modules/llms.md
   modules/prompts.md
   modules/plugins.md
   modules/connections.rst
   modules/knowledge.rst
   modules/vector.rst

Resources
-----------------

| Additional resources we think may be useful as you develop your application!

- `Discord <https://discord.gg/eZHE94MN>`_: if your have some problem or ideas, you can talk from discord.

.. toctree::
   :maxdepth: 1
   :caption: Resources
   :name: resources
   :hidden:
