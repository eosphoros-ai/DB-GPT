# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/2/1 上午10:11
'''
import json
import requests
from db.ConnectGP import pythonGP


def requests_post():
    lines1 = '''}
{'''
    with open('/datas/liab/DB-GPT-main/evaluation/evaluation_output/new_test_dataset_0225.jsonl', 'r') as f:
        assmble = '[' + f.read().replace(lines1, '},{') + ']'
        content = eval(assmble)
    # print(content)
    for con in content[:]:
        print(con['user_input'])
        url = 'http://172.23.52.25:50001/api/v1/chat/completions'
        request_payload = {'chat_mode': "chat_with_db_execute",
                           'conv_uid': "622ce118-bde2-11ee-8811-bc97e1765950",
                           'model_name': "proxyllm",
                           'select_param': "hr_chinese_fk",
                           'user_input': con['user_input']}
        print(requests.post(url, json=request_payload))


def data_result_analyze():
    '''
    result_type1_version1: {"数据版本":"type1","rag逻辑":"Embedding过滤出6张表；交给GPT4进行rerank。生成table_infos","拓展内容":"整块的extend"}
    '''
    path1 = '/datas/liab/DB-GPT-main/evaluation/evaluation_output/result_type1_version1.jsonl'
    gp_host = '172.23.10.250'
    gp_port = '5432'

    gp_user = 'chatgpt'
    gp_password = 'chatgpt'
    lines1 = '''}
{'''

    with open(path1, 'r') as f:
        assmble = '[' + f.read().replace(lines1, '},{') + ']'
        content1 = eval(assmble)

    path2 = '/datas/liab/DB-GPT-main/evaluation/evaluation_output/result_type1_version3.jsonl'
    with open(path2, 'r') as f:
        assmble = '[' + f.read().replace(lines1, '},{') + ']'
        content2 = eval(assmble)

    path3 = '/datas/liab/DB-GPT-main/evaluation/evaluation_output/compare_type1_version1_version3.jsonl'
    compare_list = []
    i = 0
    # 以 version1 为基准
    for con1, con2 in zip(content1, content2):
        gp1 = pythonGP(host=gp_host, port=gp_port, dbname=con1['db_name'], user=gp_user, password=gp_password)
        gp2 = pythonGP(host=gp_host, port=gp_port, dbname=con2['db_name'], user=gp_user, password=gp_password)
        res1 = None
        res2 = None
        sql1 = None
        sql2 = None
        if con1['user_input'] == con2['user_input']:
            sql1 = con1.get('sql')
            sql2 = con2.get('sql')

            if sql1:
                try:
                    res1 = gp1.queryGP(con1['sql'])
                except:
                    res1 = None
            if sql2:
                try:
                    res2 = gp2.queryGP(con2['sql'])
                except:
                    res2 = None
        else:
            print('error')
        user_input = con1['user_input']
        i += 1
        dict_temp = {
            'user_input': user_input,
            'index': i,
            'sql1': sql1,
            'sql2': sql2,
            'res1': res1.to_markdown() if res1 is not None else None,
            'res2': res2.to_markdown() if res2 is not None else None,
        }

        compare_list.append(dict_temp)
    with open(path3, 'w') as f:
        f.write(json.dumps(compare_list, indent=4, ensure_ascii=False))


if __name__ == '__main__':
    requests_post()
