# DB-GPT
A Open Database-GPT Experiment

![GitHub Repo stars](https://img.shields.io/github/stars/csunny/db-gpt?style=social)

DB-GPT is an experimental open-source application that builds upon the fastchat model and uses vicuna as its base model. Additionally, it looks like this application incorporates langchain and llama-index embedding knowledge to improve Database-QA capabilities. 

Overall, it appears to be a sophisticated and innovative tool for working with databases. If you have any specific questions about how to use or implement DB-GPT in your work, please let me know and I'll do my best to assist you.

# Install
1. Run model server
```
cd pilot/server
uvicorn vicuna_server:app --host 0.0.0.0
```

2. Run gradio webui
```
python app.py 
```

# Featurs
- SQL-Generate
- Database-QA Based Knowledge 
- SQL-diagnosis