# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/11 上午9:40
'''

from db.ConnectGP import pythonGP
import pandas as pd
import json

from db.ConnectOracle import connectOracle

db = pythonGP(host='172.23.10.249', port='5432', dbname='hr_chinese_fk', user='postgres', password='labpassword')
table_name = 'a_sap_reporting_relationship_chinese'
sql = f'''

drop table if exists public.{table_name};
create table public.{table_name}(
开始日期  date null,
结束日期  date null,           
人员工号  integer PRIMARY KEY,   
姓名  varchar(60) null,
入司日期  date null,
工作性质  varchar(40) null,
一级机构  varchar(40) null,
二级机构  varchar(40) null,
三级机构  varchar(40) null,
是否管理机构  varchar(40) null,
主管1姓名  varchar(40) null,
主管1职位  varchar(100) null,
主管1职务  varchar(40) null,
主管2姓名  varchar(40) null, 
主管2职位  varchar(1000) null,
主管2职务  varchar(40) null,
经理1姓名  varchar(40) null,
经理1职位  varchar(100) null,
经理1职务  varchar(40) null,
经理2姓名  varchar(40) null,
经理2职位  varchar(100) null,
经理2职务  varchar(40) null,
经理3姓名  varchar(40) null,
经理3职位  varchar(100) null,
经理3职务  varchar(40) null,
经理4姓名  varchar(40) null,
经理4职位  varchar(100) null,
经理4职务  varchar(40) null,
总监1姓名  varchar(40) null,
总监1职位  varchar(100) null,
总监1职务  varchar(40) null,
总监2姓名  varchar(40) null,
总监2职位  varchar(100) null,
总监2职务  varchar(40) null,
总监3姓名  varchar(40) null,
总监3职位  varchar(100) null,
总监3职务  varchar(40) null,
总监4姓名  varchar(40) null,
总监4职位  varchar(100) null,
总监4职务  varchar(40) null,
一级机构负责人姓名  varchar(40) null,
一级机构负责人职位  varchar(100) null,
一级机构负责人职务  varchar(40) null,
CONSTRAINT fk_report_basic_info
  FOREIGN KEY(人员工号) 
  REFERENCES a_sap_employee_information_chinese(人员工号)
  ON UPDATE CASCADE 
  ON DELETE CASCADE
);

COMMENT ON TABLE public.{table_name} IS '公司所有员工汇报关系表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.{table_name}.开始日期 IS '汇报关系开始的时间';
COMMENT ON COLUMN public.{table_name}.结束日期 IS '汇报关系结束的时间';
COMMENT ON COLUMN public.{table_name}.人员工号 IS '该表主键，每个员工的唯一id值。';
COMMENT ON COLUMN public.{table_name}.工作性质 IS '值为：["全职-计算","挂职","兼职-不计算","劳务外包"]';

COMMENT ON COLUMN public.{table_name}.一级机构 IS '也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等';
COMMENT ON COLUMN public.{table_name}.二级机构 IS '也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等';
COMMENT ON COLUMN public.{table_name}.三级机构 IS '也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等';
COMMENT ON COLUMN public.{table_name}.是否管理机构 IS '该员工是否是部门（一级机构），小组（二级机构，三级机构）负责人。值为：["是","否"]';

grant select,insert, update, delete on table public.{table_name} to chatgpt;
GRANT ALL PRIVILEGES ON SCHEMA public TO chatgpt;
'''

columns_name_dict = {

    'begda': '开始日期', 'endda': '结束日期,', 'pernr': '人员工号', 'ename': '姓名,', 'startda': '入司日期,', 'zgzxz': '工作性质,', 'orgt1': '一级机构,', 'orgt2': '二级机构,', 'orgt3': '三级机构,', 'orgt4': '四级机构,', 'orgt5': '五级机构,',
    'orgt6': '六级机构,', 'orgt7': '七级机构,', 'orgt8': '八级机构,', 'orgt9': '九级机构,', 'orgt10': '十级机构,', 'stext': '职位,', 'stltx': '职务名称,', 'zifgljg': '是否管理机构,', 'zjzinfo': '兼职信息,', 'spvs1_name': '主管1姓名,',
    'spvs1_stext': '主管1职位,', 'spvs1_stltx': '主管1职务,', 'spvs2_name': '主管2姓名,', 'spvs2_stext': '主管2职位,', 'spvs2_stltx': '主管2职务,', 'spvs3_name': '主管3姓名,', 'spvs3_stext': '主管3职位,',
    'spvs3_stltx': '主管3职务,', 'mngr1_name': '经理1姓名,', 'mngr1_stext': '经理1职位,', 'mngr1_stltx': '经理1职务,', 'mngr2_name': '经理2姓名,', 'mngr2_stext': '经理2职位,', 'mngr2_stltx': '经理2职务,', 'mngr3_name': '经理3姓名,',
    'mngr3_stext': '经理3职位,', 'mngr3_stltx': '经理3职务,', 'mngr4_name': '经理4姓名,', 'mngr4_stext': '经理4职位,', 'mngr4_stltx': '经理4职务,', 'mngr5_name': '经理5姓名,', 'mngr5_stext': '经理5职位,',
    'mngr5_stltx': '经理5职务,', 'drct1_name': '总监1姓名,', 'drct1_stext': '总监1职位,', 'drct1_stltx': '总监1职务,', 'drct2_name': '总监2姓名,', 'drct2_stext': '总监2职位,', 'drct2_stltx': '总监2职务,', 'drct3_name': '总监3姓名,',
    'drct3_stext': '总监3职位,', 'drct3_stltx': '总监3职务,', 'drct4_name': '总监4姓名,', 'drct4_stext': '总监4职位,', 'drct4_stltx': '总监4职务,', 'drct5_name': '总监5姓名,', 'drct5_stext': '总监5职位,',
    'drct5_stltx': '总监5职务,', 'frpsr_name': '一级机构负责人姓名', 'frpsr_stext': '一级机构负责人职位,', 'frpsr_stltx': '一级机构负责人职务', }

columns_name_dict_new = {'begda': '开始日期', 'endda': '结束日期', 'pernr': '人员工号', 'ename': '姓名', 'startda': '入司日期', 'zgzxz': '工作性质', 'orgt1': '一级机构', 'orgt2': '二级机构', 'orgt3': '三级机构', 'zifgljg': '是否管理机构',
                         'spvs1_name': '主管1姓名', 'spvs1_stext': '主管1职位', 'spvs1_stltx': '主管1职务', 'spvs2_name': '主管2姓名', 'spvs2_stext': '主管2职位', 'spvs2_stltx': '主管2职务', 'mngr1_name': '经理1姓名',
                         'mngr1_stext': '经理1职位', 'mngr1_stltx': '经理1职务', 'mngr2_name': '经理2姓名', 'mngr2_stext': '经理2职位', 'mngr2_stltx': '经理2职务', 'mngr3_name': '经理3姓名', 'mngr3_stext': '经理3职位',
                         'mngr3_stltx': '经理3职务', 'mngr4_name': '经理4姓名', 'mngr4_stext': '经理4职位', 'mngr4_stltx': '经理4职务', 'drct1_name': '总监1姓名', 'drct1_stext': '总监1职位', 'drct1_stltx': '总监1职务',
                         'drct2_name': '总监2姓名', 'drct2_stext': '总监2职位', 'drct2_stltx': '总监2职务', 'drct3_name': '总监3姓名', 'drct3_stext': '总监3职位', 'drct3_stltx': '总监3职务', 'drct4_name': '总监4姓名',
                         'drct4_stext': '总监4职位', 'drct4_stltx': '总监4职务', 'frpsr_name': '一级机构负责人姓名', 'frpsr_stext': '一级机构负责人职位', 'frpsr_stltx': '一级机构负责人职务'}

aa = [j for j in columns_name_dict_new.items()]
for i in aa[::-1]:
    sql = sql.lower().replace(i[0], i[1])

print(sql)

print(db.excuSql(sql))

useless_col = ['orgt0', 'etl_date', 'orgh0', 'plans_t']
msk_col = ['ename', 'spvs1_name', 'spvs2_name', 'spvs3_name', 'mngr1_name', 'mngr2_name', 'mngr3_name', 'mngr4_name', 'mngr5_name', 'drct1_name', 'drct2_name', 'drct3_name', 'drct4_name',
           'drct5_name', 'frpsr_name', 'pernr', 'spvs1', 'spvs2', 'spvs3', 'mngr1', 'mngr2', 'mngr3', 'mngr4', 'mngr5', 'drct1', 'drct2', 'drct3', 'drct4', 'drct5', 'frpsr']

int2str = ['pernr', 'spvs1', 'spvs2', 'spvs3', 'mngr1', 'mngr2', 'mngr3', 'mngr4', 'mngr5', 'drct1', 'drct2', 'drct3', 'drct4', 'drct5', 'frpsr']
blob2str = ['mngr3_stext']

sql = '''
SELECT * FROM hzuser.a_sap_reporting_relationship_ai
    '''
# # 连接数据库的功能初始化
db_oracle = connectOracle()
df = db_oracle.queryOracle(sql)
new_columns = [i.lower() for i in df.columns.tolist()]

df.columns = new_columns

df[int2str] = df[int2str].astype(int).astype(str)
df[blob2str] = df[blob2str].astype(str)

# df[msk_col] = df[msk_col].applymap(lambda x:getDictValues(name_id_msk_json,x))


df = df.rename(columns=columns_name_dict_new)
need_col = list(columns_name_dict_new.values())

# sql_text_list = sql.split('\n')
# table_sql = sql_text_list
#
# new_sql_list = []
# for nc in need_col:
#     for st in sql_text_list:
#         if nc in st:
#             new_sql_list.append(st)
#             sql_text_list
# print('\n'.join(new_sql_list))


df = df[need_col]

# df.to_csv('reporting_relationship.csv',encoding='GBK',index=False)

db.insertGP(df, 'public', table_name)
