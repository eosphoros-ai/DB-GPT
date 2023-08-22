Chat DB FAQ
==================================

##### Q1: What difference between ChatData and ChatDB

ChatData generates SQL from natural language and executes it. ChatDB involves conversing with metadata from the
Database, including metadata about databases, tables, and fields.

##### Q2: The suitable llm model currently supported for text-to-SQL is?

Now vicunna-13b-1.5 and llama2-70b is more suitable for text-to-SQL.

##### Q3: How to fine-tune Text-to-SQL in DB-GPT

there is another github project for Text-to-SQL fine-tune (https://github.com/eosphoros-ai/DB-GPT-Hub)

##### Q4: chatdata with clickhouse clickhouse-sqlalchemy 0.2.4 requires sqlalchemy<1.5,>=1.4.24, but you have sqlalchemy 2.0.20 which is incompatible

Just set sqlalchemy<1.5,>=1.4.24

```commandline
pip install clickhouse-driver
pip install sqlalchemy==1.4.24
```