# Chat With Financial Report 
# Description
Upload financial report pdf and chat with financial report
scene1:ask base info for financial report
![base_info_chat](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/3091aa7b-b2e5-4f95-ba63-182bfa902039)
scene2:calculate financial indicator for financial report
![fin_indicator_chat](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/b0926d30-11af-4080-b2f7-2c6fcf895d58)




# How Has This Been Tested?

Step 1: upgrade `knowledge_space`
```sql
USE dbgpt;
ALTER TABLE  knowledge_space
    ADD COLUMN `domain_type` varchar(50) null comment 'space domain type' after `vector_type`;
```
Step 2: upgrade python dependencies
```
pip install pdfplumber
pip install fuzzywuzzy
```

Step3: 
download classifier pre_trained model from https://huggingface.co/luchun/bge_fin_intent_large_zh_v1.5/tree/main
download pkl classifier model from`DB-GPT/docker/examples/fin_report/model/logistic_regression_model.pkl`
and set in `.env`
```
#*******************************************************************#
#**                     FINANCIAL CHAT Config                     **#
#*******************************************************************#
FIN_REPORT_MODEL=/app/model/bge_fin_intent_large_zh_v1.5
FIN_CLASSIFIER_PKL=DB-GPT/docker/examples/fin_report/model/logistic_regression_model.pkl
```
Step 4: restart dbgpt_server

Step 5: create financial report knowledge space
![financial_space](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/77b642aa-0c38-416c-8809-9cfce130140f)
Step 6: upload financial report from `docker/examples/fin_report`
![upload_report](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/4630f226-4bd6-4645-858a-bd3cde4e4789)
Step 7:  automatic segment and wait for a while
![process_log](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/0506dd86-4089-4ba4-8589-b617afc0eafe)
Step 8:  chat with financial report

