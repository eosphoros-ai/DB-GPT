ChatData & ChatDB
==================================
ChatData generates SQL from natural language and executes it. ChatDB involves conversing with metadata from the
Database, including metadata about databases, tables, and
fields.![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/d8bfeee9-e982-465e-a2b8-1164b673847e)

### 1.Choose Datasource

If you are using DB-GPT for the first time, you need to add a data source and set the relevant connection information
for the data source.

```{tip}
there are some example data in DB-GPT-NEW/DB-GPT/docker/examples

you can execute sql script to generate data.
```

#### 1.1 Datasource management

![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/7678f07e-9eee-40a9-b980-5b3978a0ed52)

#### 1.2 Connection management

![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/25b8f5a9-d322-459e-a8b2-bfe8cb42bdd6)

#### 1.3 Add Datasource

![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/19ce31a7-4061-4da8-a9cb-efca396cc085)

```{note}
now DB-GPT support Datasource Type

* Mysql
* Sqlite
* DuckDB
* Clickhouse
* Mssql
```

### 2.ChatData
##### Preview Mode
After successfully setting up the data source, you can start conversing with the database. You can ask it to generate
SQL for you or inquire about relevant information on the database's metadata.
![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/8acf6a42-e511-48ff-aabf-3d9037485c1c)

##### Editor Mode
In Editor Mode, you can edit your sql and execute it.
![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/1a896dc1-7c0e-4354-8629-30357ffd8d7f)


### 3.ChatDB

![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/e04bc1b1-2c58-4b33-af62-97e89098ace7)


