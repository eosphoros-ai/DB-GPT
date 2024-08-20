# Chat With Financial Report
   Financial report analysis using large models is becoming a popular application in vertical fields. Large models can not only understand complex financial rules more accurately than humans, but can also output reasonable analysis results based on professional knowledge. 
   
Using AWEL to build a financial report knowledge building workflow and a financial report intelligent Q&A workflow app can help users 
- answer basic information questions about financial reports
- financial report indicator calculation and analysis questions
- financial report content analysis questions.

#### financial report knowledge building workflow
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/knowledge_workflow.png'} width="1000px"/>
</p>

#### a financial report intelligent robot workflow 
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/financial_robot_chat.png'} width="1000px"/>
</p>

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

Step 4: download pre_trained embedding model from https://www.modelscope.cn/models/AI-ModelScope/bge-large-zh-v1.5
```
git clone https://www.modelscope.cn/models/AI-ModelScope/bge-large-zh-v1.5
```

```
#*******************************************************************#
#**                     FINANCIAL CHAT Config                     **#
#*******************************************************************#
FIN_REPORT_MODEL=/app/DB-GPT/models/bge-large-zh-v1.5
```

Step 5: create  knowledge space, choose `FinancialReport` doamin type
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/financial_space.png'} width="1000px"/>
</p>


Step 6: upload financial report from `docker/examples/fin_report`, if your want to use the financial report dataset, you can download from modelscope.
```bash
git clone http://www.modelscope.cn/datasets/modelscope/chatglm_llm_fintech_raw_dataset.git
```
Step 7:  automatic segment and wait for a while

Step 8:  chat with financial report
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/chat.jpg'} width="1000px"/>
</p>



