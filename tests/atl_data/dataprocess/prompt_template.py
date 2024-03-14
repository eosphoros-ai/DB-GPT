# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/1/10 下午1:24
'''
import json
import openai

from tables_infos import tables_schema

api_key = 'd5d6175b7e0b411ebf5d675769b4a87c'
api_base = 'https://gpt001-7.openai.azure.com/'
api_type = 'azure'
api_version = "2023-07-01-preview"
gpt4_deployment_name = 'gpt-4-0314'

openai.api_key = api_key
openai.api_base = api_base
openai.api_type = api_type
openai.api_version = api_version

prompt_template = '''
公司相关信息如下：
```
员工工作性质文本字段的值为：["全职-计算","挂职"]
"公司财年 Txxx 对应年份规则":"T127对应2022年，T128对应2023年;按此规律回答问题中的财年对应的年份";
"年份对应规则":"今年是2023年，去年是2022年，前年是2021年;按此规律回答问题中对应的年份";
"季度Q(1~4)对应规则":"Q1-4,5,6月份,Q2-7,8,9月份,Q3-10,11,12月份,Q4-1,2,3月份";
'学历对应规则':'本科-大学本科, 研究生-硕士';
'MRD|IDT|APD|CPD|RI|CL|HR':'属于一级机构，但不限于这些，所有的一级机构还是要去数据库中查询';
'二级机构包括但不限于':'AI';
'职务顺序,从小到大排序,':'技术员-资深技术员-职员-经理-总监-副总裁-总裁';
'技术员包含这个文字内容':'技术员';
'资深技术员包括':'一级资深组长|二级资深组长',
'职员包括':'工程师|工程师1|资深工程师|工程师2|资深工程师1|资深工程师2',
'经理职务包括':'主任工程师|经理1|主任工程师1|主任|资深主任工程师|经理2|主任工程师2|资深经理',
'总监包括':'总工|首席专家|资深总监',
'副总裁包括':'高级副总裁|执行副总裁|首席技术官|董事长|荣誉董事长',
'员工子组[含义:字段]':['普工'：'一级员工', '技术员'：'二级员工','工程师'：'三级员工','中层管理层'：'四级员工','高层管理层'：'五级员工','挂职人员|CJR':'残疾人','外聘顾问'：'顾问','实习员工'：'实习'];
'雇佣状态':'默认是"在职"';
'部门':'一级机构',
技术员层级的职级范围：JG4-6
工程师层级的职级范围：JG7-10
经理层级的职级范围：JG11-13
员工的工龄是当前时间减去开始参加工作日期
```
==============================================================
我现在有几张公司的HR部门的表如下：
```
{tables_schema}
```
==============================================================
请你站在资深HR的角度，问5个问题，问题要求如下：sql难度最高，跨表查询，聚类查询，逻辑复杂。

返回类型为list(json)格式，json字段为【“difficulty”，“question”，“answer”，“thoughts”】，返回禁止生成其他内容。

'''.format(tables_schema=tables_schema)


for _ in range(1):
    print(f'第 {_+1} 次' , )
    response = openai.ChatCompletion.create(engine=gpt4_deployment_name,
                                            messages=[{'role': "user", "content": prompt_template}],
                                            temperature=0.9,
                                            n=2)
    print(response['choices'])
    for res in response['choices']:
        try:
            qs = eval(res['message']['content'].strip('```').strip('json'))
        except:continue

        for q in qs:
            with open('test.jsonl', 'a') as f:

                json.dump(
                    q,
                    f,
                    ensure_ascii=False,
                    indent=None)
                f.write('\n')

    print(response['usage'])





