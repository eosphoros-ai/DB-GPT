# DB-GPT
A Open Database-GPT Experiment

![GitHub Repo stars](https://img.shields.io/github/stars/csunny/db-gpt?style=social)


DB-GPT is an experimental open-source application that builds upon the fastchat model and uses vicuna as its base model. Additionally, it looks like this application incorporates langchain and llama-index embedding knowledge to improve Database-QA capabilities. 

Overall, it appears to be a sophisticated and innovative tool for working with databases. If you have any specific questions about how to use or implement DB-GPT in your work, please let me know and I'll do my best to assist you.

```HTML
<video width="500" height="250" controls="controls">
    <source src="https://github.com/csunny/DB-GPT/blob/dev/asserts/%E6%BC%94%E7%A4%BA.mov" type="video/mov">
</video>
```
Run on an RTX 4090 GPU (not sped up!)

- ![SQL生成示例](https://github.com/csunny/DB-GPT/blob/dev/asserts/sql_generate.png)
- ![数据库QAs示例](https://github.com/csunny/DB-GPT/blob/dev/asserts/DB_QA.png)
# Install
1. Run model server
```
cd pilot/server
python vicuna_server.py
```

2. Run gradio webui
```
python webserver.py 
```

# Featurs
- SQL-Generate
- Database-QA Based Knowledge 
- SQL-diagnosis