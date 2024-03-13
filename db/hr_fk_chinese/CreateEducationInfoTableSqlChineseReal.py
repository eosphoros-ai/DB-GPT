# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/11 上午9:37
'''
from db.ConnectGP import pythonGP
import pandas as pd
import json

from db.ConnectOracle import connectOracle

# db = pythonGP(host='172.23.10.249', port='5432', dbname='postgres', user='chatgpt', password='chatgpt')
db = pythonGP(host='172.23.10.249', port='5432', dbname='hr_chinese_fk', user='postgres', password='labpassword')

table_name = 'a_sap_employee_education_experience_chinese'

sql = f'''

drop table if exists public.{table_name};

create table public.{table_name}(

人员工号 integer PRIMARY KEY,     
姓名  text null , 
开始日期  date null, 
结束日期  date null,
学历  text null,
教育类型  text null,     
院校_培训机构  text null,
国家  text null,
证书  text null,
第一专业  text null,
CONSTRAINT fk_education_basic_info
  FOREIGN KEY(人员工号) 
  REFERENCES a_sap_employee_information_chinese(人员工号)
  ON UPDATE CASCADE 
  ON DELETE CASCADE
);

COMMENT ON TABLE public.{table_name} IS '公司所有员工受教育经历的数据表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.{table_name}.人员工号 IS '每个员工的唯一工号，也是这张表的主键';
COMMENT ON COLUMN public.{table_name}.开始日期 IS '受教育的开始日期';
COMMENT ON COLUMN public.{table_name}.结束日期 IS '受教育的结束日期';
COMMENT ON COLUMN public.{table_name}.学历 IS '值：["硕士","高中","大学专科","博士","初中及以下","大学本科","中专"]';

grant select,insert, update, delete on table public.{table_name} to chatgpt;
GRANT ALL PRIVILEGES ON SCHEMA public TO chatgpt;
'''

columns_name_dict = {'pernr': '人员工号', 'slabs_stext': '证书', 'ename': '姓名', 'stext': '学历', 'begda': '开始日期', 'endda': '结束日期', 'insti': '院校_培训机构', 'sland': '国家', 'atext': '教育类型', 'zzhye': '第一专业', }

for i in columns_name_dict.items():
    sql = sql.replace(i[0], i[1])
print(sql)
print(db.excuSql(sql))

useless_col = []
msk_col = ['pernr', 'ename']

sql = '''
SELECT * FROM hzuser.a_sap_employee_education_information_ai
    '''
# # 连接数据库的功能初始化
db_oracle = connectOracle()
df = db_oracle.queryOracle(sql)
new_columns = [i.lower() for i in df.columns.tolist()]
df.columns = new_columns

# df[msk_col] = df[msk_col].applymap(lambda x:getDictValues(name_id_msk_json,x))

df = df.rename(columns=columns_name_dict)
df.drop_duplicates(subset=['人员工号'], inplace=True)

need_col = list(columns_name_dict.values())

# df = df.drop(useless_col,axis=1)
df = df[need_col]
# df.to_csv('education_info.csv',encoding='GBK',index=False)
db.insertGP(df, 'public', table_name)