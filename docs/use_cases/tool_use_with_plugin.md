# Tool use with plugin

- DB-GPT supports a variety of plug-ins, such as BaiduSearch, SendEmail. In addition, some database management platforms can also package their interfaces and package them into plug-ins, and use the model to realize the ability of "single-sentence requirements"


## Baidu-Search-Plugin

[Db-GPT Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins/blob/main/src/dbgpt_plugins/Readme.md)

- Perform search queries using the Baidu search engine  [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins).

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

- More detail see: [DB-DASHBOARD](https://github.com/eosphoros-ai/DB-GPT-Plugins/blob/main/src/dbgpt_plugins/Readme.md)

