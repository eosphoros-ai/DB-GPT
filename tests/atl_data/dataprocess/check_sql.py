# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/1/10 下午5:09
'''
import json
from db.ConnectGP import pythonGP

db = pythonGP(host='172.23.10.249', port='5432', dbname='hr_chinese_fk', user='postgres', password='labpassword')

with open('/datas/liab/FinGLM/code/ATL/dataset/prompt.jsonl', 'r') as f:
    lines = f.readlines()
    contents = [json.loads(line.strip()) for line in lines]

with open('/datas/liab/FinGLM/code/ATL/dataset/prompt_check_sql.jsonl', 'w') as f:
    f.write('')
with open('/datas/liab/FinGLM/code/ATL/dataset/prompt_check_sql_error.jsonl', 'w') as f:
    f.write('')
for con in contents:
    try:
        res = db.queryGP(con['answer'])
        print(con['question'],'||',res)

        with open('/datas/liab/FinGLM/code/ATL/dataset/prompt_check_sql.jsonl','a') as f:
            json.dump(
                con,
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')
    except Exception as e:
        print('\t[ERROR] ',e)

        with open('/datas/liab/FinGLM/code/ATL/dataset/prompt_check_sql_error.jsonl', 'a') as f:
            json.dump(
                con,
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')
        continue