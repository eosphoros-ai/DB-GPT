
## 官网部署

- 官网部署流程

```commandline
git clone https://github.com/eosphoros-ai/DB-GPT

git checkout feature-auth
```

- 配置.env文件

```commandline
cp .env.template .env
# 然后根据自身情况修改当前数据
```

- 配置用户体验数据
```text 
chatDB: 设置一个public库/test库，允许用户可见
chatKnowledge: 启动之后会在本地embedding一个知识空间（Professional DBA）: MySQL|MongoDB|Spark 专业文档Embedding
```


```commandline
nohup python pilot/server/dbgpt_server > /usr/logs/dbgpt_server.log &

```





