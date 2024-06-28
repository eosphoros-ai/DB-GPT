# Database Resource

The database resource `DBResource` is a resource that can be used to interact with databases. 
It is a subclass of the `Resource` class and provides a way to interact with databases.

Here are some implementations of the `DBResource` class:
- `RDBMSConnectorResource`: A resource that can be used to connect to a relational database management system (RDBMS) like MySQL, PostgreSQL, etc.
- `SQLiteDBResource`: A specific implementation of the `RDBMSConnectorResource` class that can be used to connect to a SQLite database.
- `DatasourceResource`: A resource that can be used to connect to various data sources in DB-GPT.
It just works when you run your agent in the DB-GPT environment(running in the DB-GPT webserver).

In previous sections [Agents With Database](../../introduction/database), we have introduced 
how to use the database resource in the DB-GPT agent, so you can refer to it for more details.

## How It Works

(Coming soon...)