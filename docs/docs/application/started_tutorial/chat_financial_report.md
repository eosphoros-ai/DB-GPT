# Chat With Financial Report 
    
   Recently, financial analysis with the help of large models is becoming a popular application in vertical fields. Large models can not only understand complex financial rules more accurately than humans, but can also output reasonable analysis results based on professional knowledge. Many cutting-edge solutions have provided answers such as RAG and Agent. However, financial statement information is large and complex, and the accuracy of data analysis is extremely high. It is difficult for general solutions to meet these needs.

For example, when a user queries "What is the operating net profit of XXX subsidiary in 2022?", the conventional method is to recall the most relevant text blocks for summary and question and answer through knowledge vector similarity retrieval and matching. However, the annual financial report contains many relevant information that may lead to misjudgment. If you cannot accurately recall and understand the correct part, it is easy to generate wrong answers.

In order to overcome some obstacles in the application of large models, we need to combine the knowledge background in the financial field and add specialized external modules to enhance its functions. This article will take DB-GPT's Awel orchestration mode as an example, and use several key atoms of DB-GPT-Hub to describe how to use large models to conduct effective financial report data analysis.

# How to Use
Upload financial report pdf and chat with financial report

scene1:ask base info for financial report

<p align="left">
  <img src={'/img/chat_knowledge/fin_report/base_info_chat.jpg'} width="1000px"/>
</p>

scene2:calculate financial indicator for financial report
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/chat_indicator.png'} width="1000px"/>
</p>

scene3:analyze financial report
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/report_analyze.png'} width="1000px"/>
</p>


# How to Install

Step 1: make sure your dbgpt version is >=0.5.10
```
Step 2: upgrade python dependencies
```
pip install pdfplumber
pip install fuzzywuzzy
```
Step 3: install financial report app from dbgpts
```
# install poetry
pip install poetry

# install financial report knowledge process pipeline workflow and financial-robot-app workflow
dbgpt app install financial-robot-app financial-report-knowledge-factory

```

Step4: 
download pre_trained embedding model from https://www.modelscope.cn/models/AI-ModelScope/bge-large-zh-v1.5
```
git clone https://www.modelscope.cn/models/AI-ModelScope/bge-large-zh-v1.5
```

```
#*******************************************************************#
#**                     FINANCIAL CHAT Config                     **#
#*******************************************************************#
FIN_REPORT_MODEL=/app/DB-GPT/models/bge-large-zh-v1.5
```

Step 4: create FinancialReport knowledge space
![image](https://github.com/user-attachments/assets/90d938f0-e09f-49f2-8f8b-fa69ef6f8ae6)

Step 5: upload financial report from `docker/examples/fin_report`
![upload_report](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/4630f226-4bd6-4645-858a-bd3cde4e4789)
Step 6:  automatic segment and wait for a while
![process_log](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/0506dd86-4089-4ba4-8589-b617afc0eafe)
Step 7:  chat with financial report



