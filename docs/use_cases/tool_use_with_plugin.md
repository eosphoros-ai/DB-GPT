# Tool use with plugin

- DB-GPT supports a variety of plug-ins, such as MySQL, MongoDB, ClickHouse and other database tool plug-ins. In addition, some database management platforms can also package their interfaces and package them into plug-ins, and use the model to realize the ability of "single-sentence requirements"


## DB-GPT-DASHBOARD-PLUGIN

[](https://github.com/csunny/DB-GPT-Plugins/blob/main/src/dbgpt_plugins/Readme.md)

- This is a DB-GPT plugin to generate data analysis charts, if you want to use the test sample data, please first pull the code of [DB-GPT-Plugins](https://github.com/csunny/DB-GPT-Plugins), run the command to generate test DuckDB data, and then copy the generated data file to the `/pilot/mock_datas` directory of the DB-GPT project.

```bash
git clone https://github.com/csunny/DB-GPT-Plugins.git
pip install -r requirements.txt
python /DB-GPT-Plugins/src/dbgpt_plugins/db_dashboard/mock_datas.py 
cp /DB-GPT-Plugins/src/dbgpt_plugins/db_dashboard/mock_datas/db-gpt-test.db /DB-GPT/pilot/mock_datas/

python /DB-GPT/pilot/llmserver.py
python /DB-GPT/pilot/webserver.py
```
- Test Case: Use a histogram to analyze the total order amount of users in different cities.
<p align="center">
  <img src="../../assets/dashboard.png" width="680px" />
</p>

- More detail see: [DB-DASHBOARD](https://github.com/csunny/DB-GPT-Plugins/blob/main/src/dbgpt_plugins/Readme.md)


## DB-GPT-SQL-Execution-Plugin


- This is an DbGPT plugin to connect Generic Db And Execute SQL.


## DB-GPT-Bytebase-Plugin

- To use a tool or platform plugin, you should first deploy a plugin. Taking the open-source database management platform Bytebase as an example, you can deploy your Bytebase service with one click using Docker and access it at http://127.0.0.1:5678. More details can be found at https://github.com/bytebase/bytebase.
```bash
docker run --init \
  --name bytebase \
  --platform linux/amd64 \
  --restart always \
  --publish 5678:8080 \
  --health-cmd "curl --fail http://localhost:5678/healthz || exit 1" \
  --health-interval 5m \
  --health-timeout 60s \
  --volume ~/.bytebase/data:/var/opt/bytebase \
  bytebase/bytebase:2.2.0 \
  --data /var/opt/bytebase \
  --port 8080
```

Note: If your machine's CPU architecture is `ARM`, please use `--platform linux/arm64` instead.

- Select the plugin on DB-GPT（All built-in plugins are from our repository: https://github.com/csunny/DB-GPT-Plugins），choose DB-GPT-Bytebase-Plugin. 
Supporting functions include creating projects, creating environments, creating database instances, creating databases, database DDL/DML operations, and ticket approval process, etc.

