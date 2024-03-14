# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/1/15 上午8:21
'''

import json
import rich
from tables_infos import tables_schema
from department_data import first_departments, second_departments

graduate = [
    {'question': '研究生', 'answer': '硕士'},
    {'question': '大学本科', 'answer': '本科'},
    {'question': '硕士', 'answer': '硕士'},
    {'question': '博士', 'answer': '博士'},
]

fin_year = [
    {'question': 'T128', 'answer': 'T128'},
    {'question': 'T127', 'answer': 'T127'},
    {'question': 'T126', 'answer': 'T126'},
    {'question': 'T125', 'answer': 'T125'},
    {'question': 'T124', 'answer': 'T124'},
    {'question': 'T123', 'answer': 'T123'},
]

month_year = [
    {'question': '8', 'answer': '8'},
    {'question': '9', 'answer': '9'},
    {'question': '7', 'answer': '7'},
    {'question': '12', 'answer': '12'},
    {'question': '6', 'answer': '6'},
    {'question': '11', 'answer': '11'},
    {'question': '5', 'answer': '5'},
    {'question': '10', 'answer': '10'},
    {'question': '4', 'answer': '4'},
    {'question': '2', 'answer': '2'},
    {'question': '3', 'answer': '3'},
    {'question': '1', 'answer': '1'},
]
season_year = [
    {'question': '第一季度', 'answer': "'4','5','6'"},
    {'question': 'Q1', 'answer': "'4','5','6'"},
    {'question': '第2季度', 'answer': "'7','8','9'"},
    {'question': 'Q2', 'answer': "'7','8','9'"},
    {'question': '第3季度', 'answer': "'10','11','12'"},
    {'question': 'Q3', 'answer': "'10','11','12'"},
    {'question': '第4季度', 'answer': "'1','2','3'"},
    {'question': 'Q4', 'answer': "'1','2','3'"},
]

a = '/datas/liab/RAGTest/dataset/prompt_true_data_enhance_tmp2.jsonl'
new = '/datas/liab/RAGTest/dataset/prompt_true_data_enhance_tmp2.jsonl'

with open(a, 'r') as f:
    contents = [json.loads(line) for line in f.readlines()]


def replace_data():
    new_contents = []

    for content in contents:
        if '[部门]' in content['question']:
            for department in first_departments:
                print(content['question'].replace('[部门]', department['shortname']),
                      content['answer'].replace('[部门]', department['shortname']))
                dict_tmp = {'question': content['question'].replace('[部门]', department['shortname']),
                            'answer': content['answer'].replace('[部门]', department['shortname'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')
                print(content['question'].replace('[部门]', department['fullname']),
                      content['answer'].replace('[部门]', department['shortname']))
                dict_tmp = {'question': content['question'].replace('[部门]', department['fullname']),
                            'answer': content['answer'].replace('[部门]', department['shortname'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')
                print(content['question'].replace('[部门]', department['chinesename']),
                      content['answer'].replace('[部门]', department['shortname']))
                dict_tmp = {'question': content['question'].replace('[部门]', department['chinesename']),
                            'answer': content['answer'].replace('[部门]', department['shortname'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')

        if '[学历]' in content['question']:
            for g in graduate:
                dict_tmp = {'question': content['question'].replace('[学历]', g['question']),
                            'answer': content['answer'].replace('[学历]', g['answer'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')

        if '[财年]' in content['question']:
            for g in fin_year:
                dict_tmp = {'question': content['question'].replace('[财年]', g['question']),
                            'answer': content['answer'].replace('[财年]', g['answer'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')
        if '[月份]' in content['question']:
            for g in month_year:
                dict_tmp = {'question': content['question'].replace('[月份]', g['question']),
                            'answer': content['answer'].replace('[月份]', g['answer'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')
        if '[季度]' in content['question']:
            for g in season_year:
                dict_tmp = {'question': content['question'].replace('[季度]', g['question']),
                            'answer': content['answer'].replace('[季度]', g['answer'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')

        if '[二级机构]' in content['question']:
            for g in second_departments:
                dict_tmp = {
                    'question': content['question'].replace('[二级机构]', g['parent_org'] + '-' + g['shortname']),
                    'answer': content['answer'].replace('[二级机构]', g['shortname'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')

                dict_tmp = {
                    'question': content['question'].replace('[二级机构]', g['parent_org'] + '-' + g['chinesename']),
                    'answer': content['answer'].replace('[二级机构]', g['shortname'])}
                with open(new, 'a') as f:
                    json.dump(
                        dict_tmp,
                        f,
                        ensure_ascii=False,
                        indent=None)
                    f.write('\n')


def clear_data():
    new = '/datas/liab/RAGTest/dataset/prompt_true_data_enhance.jsonl'
    tem_set_dict = []
    with open(a, 'r') as f:
        contents = [json.loads(line) for line in f.readlines()]
    new_contents = []
    for c in contents:
        if '[' not in c['question']:
            new_contents.append(c)

    for c in new_contents:
        if c['question'] not in tem_set_dict:
            with open(new, 'a') as f:
                json.dump(
                    c,
                    f,
                    ensure_ascii=False,
                    indent=None)
                f.write('\n')
            tem_set_dict.append(c['question'])





def create_prompt():
    import random
    a = '/datas/liab/RAGTest/dataset/prompt_true_data_enhance.jsonl'
    with open(a, 'r') as f:
        contents = [json.loads(line) for line in f.readlines()]

    random.shuffle(contents)

    new_contents = []
    prompt_temp = '你是一名Postgres数据库开发人员，你精通Postgres数据库的sql代码编写，你需要根据已知的表名、字段名和用户输入的问题编写sql代码，以下有几张表名字。\n' + tables_schema + '\n用户输入：\n'
    t = 0
    for c in contents:
        t += 1
        new_contents.append({'question_prompt': prompt_temp, 'question': c['question'], 'answer': c['answer'], 'id': t})

    train_set, valid_set, test_set = new_contents[:int(len(new_contents) * 0.7)], new_contents[
                                                                                  int(len(new_contents) * 0.7):int(
                                                                                      len(new_contents) * 0.85)], new_contents[
                                                                                                                  int(len(
                                                                                                                      new_contents) * 0.85):]

    train_set.append(
        {'question_prompt': '员工工作性质文本字段的值为：["全职-计算","挂职"]', 'question': '', 'answer': '',
         'id': t + 1})
    train_set.append(
        {'question_prompt': '公司财年 Txxx 对应年份规则":"T127对应2022年，T128对应2023年', 'question': '', 'answer': '',
         'id': t + 1})
    train_set.append({
                         'question_prompt': '季度Q(1~4)对应规则":"{"Q1":"4,5,6月份","Q2":"7,8,9月份","Q3":"10,11,12月份","Q4":"1,2,3月份"',
                         'question': '', 'answer': '', 'id': t + 1})
    train_set.append(
        {'question_prompt': "'职务顺序,从小到大排序,':'技术员-资深技术员-职员-经理-总监-副总裁-总裁';", 'question': '',
         'answer': '', 'id': t + 1})
    train_set.append(
        {'question_prompt': "'职员包括':'工程师|工程师1|资深工程师|工程师2|资深工程师1|资深工程师2'", 'question': '',
         'answer': '', 'id': t + 1})
    train_set.append({
                         'question_prompt': "'经理职务包括':'主任工程师|经理1|主任工程师1|主任|资深主任工程师|经理2|主任工程师2|资深经理'",
                         'question': '', 'answer': '', 'id': t + 1})
    train_set.append({
                         'question_prompt': "员工子组[含义:字段]':['普工'：'一级员工', '技术员'：'二级员工','工程师'：'三级员工','中层管理层'：'四级员工','高层管理层'：'五级员工','挂职人员|CJR':'残疾人','外聘顾问'：'顾问','实习员工'：'实习']",
                         'question': '', 'answer': '', 'id': t + 1})
    train_set.append(
        {'question_prompt': "你好", 'question': '你是谁？', 'answer': '我是宁德新能源HR信息查询助手。', 'id': t + 1})


    # glm3
    train_set_path = '/datas/liab/RAGTest/dataset/conversations_glm3_train_set.jsonl'
    with open(train_set_path, 'w') as f:
        f.write('')
    for c in train_set:
        with open(train_set_path, 'a') as f:
            json.dump(
                    {'conversations': [
                        {'role': 'system', 'content': c['question_prompt']},
                        {'role': 'user', 'content': c['question']},
                        {'role': 'assistant', 'content': c['answer']},
                    ]},
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')

    valid_set_path = '/datas/liab/RAGTest/dataset/conversations_glm3_valid_set.jsonl'
    with open(valid_set_path, 'w') as f:
        f.write('')
    for c in valid_set:
        with open(valid_set_path, 'a') as f:
            json.dump(
                    {'conversations': [
                        {'role': 'system', 'content': c['question_prompt']},
                        {'role': 'user', 'content': c['question']},
                        {'role': 'assistant', 'content': c['answer']},
                    ]},
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')

    test_set_path = '/datas/liab/RAGTest/dataset/conversations_glm3_test_set.jsonl'
    with open(test_set_path, 'w') as f:
        f.write('')
    for c in test_set:
        with open(test_set_path, 'a') as f:
            json.dump(
                {'conversations': [
                    {'role': 'system', 'content': c['question_prompt']},
                    {'role': 'user', 'content': c['question']},
                    {'role': 'assistant', 'content': c['answer']},
                ]}
                ,
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')


    # formate input- output
    train_set_path = '/datas/liab/RAGTest/dataset/formate_glm3_train_set.jsonl'
    with open(train_set_path, 'w') as f:
        f.write('')
    for c in train_set:
        with open(train_set_path, 'a') as f:
            json.dump(
                {'prompt':c['question_prompt']+c['question'], 'response':c['answer']},
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')

    valid_set_path = '/datas/liab/RAGTest/dataset/formate_glm3_valid_set.jsonl'
    with open(valid_set_path, 'w') as f:
        f.write('')
    for c in valid_set:
        with open(valid_set_path, 'a') as f:
            json.dump(
                {'prompt':c['question_prompt']+c['question'], 'response':c['answer']},
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')

    test_set_path = '/datas/liab/RAGTest/dataset/formate_glm3_test_set.jsonl'
    with open(test_set_path, 'w') as f:
        f.write('')
    for c in test_set:
        with open(test_set_path, 'a') as f:
            json.dump(
                {'prompt':c['question_prompt']+c['question'], 'response':c['answer']},
                f,
                ensure_ascii=False,
                indent=None)
            f.write('\n')




    # qwen
    train_set_path = '/datas/liab/RAGTest/dataset/qwen_train_set.jsonl'
    qwen_conversations_train_set = []
    for i,c in enumerate(train_set):
        qwen_conversations_train_set.append({
            'id':i,
            'conversations': [
                {'from': 'user', 'value': c['question_prompt']+c['question']},
                {'from': 'assistant', 'value': c['answer']},
        ]})
    with open(train_set_path, 'w') as f:
        json.dump(
            qwen_conversations_train_set,
            f,
            ensure_ascii=False,
            indent=None)

    valid_set_path = '/datas/liab/RAGTest/dataset/qwen_valid_set.jsonl'
    qwen_conversations_valid_set = []
    for i,c in enumerate(valid_set):
        qwen_conversations_valid_set.append({
            'id':i,
            'conversations': [
                {'from': 'user', 'value': c['question_prompt']+c['question']},
                {'from': 'assistant', 'value': c['answer']},
        ]})
    with open(valid_set_path, 'w') as f:
        json.dump(
            qwen_conversations_valid_set,
            f,
            ensure_ascii=False,
            indent=None)

    test_set_path = '/datas/liab/RAGTest/dataset/qwen_test_set.jsonl'
    qwen_conversations_test_set = []
    for i,c in enumerate(test_set):
        qwen_conversations_test_set.append({
            'id':i,
            'conversations': [
                {'from': 'user', 'value': c['question_prompt']+c['question']},
                {'from': 'assistant', 'value': c['answer']},
        ]})
    with open(test_set_path, 'w') as f:
        json.dump(
            qwen_conversations_test_set,
            f,
            ensure_ascii=False,
            indent=None)

if __name__ == '__main__':
    create_prompt()
