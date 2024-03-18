# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/11 上午9:51
'''

from db.ConnectGP import pythonGP
from db.ConnectOracle import connectOracle
import sys

if len(sys.argv) > 1:
    dbname = sys.argv[1]
else:
    dbname = 'hr_chinese_fk'
db = pythonGP(host='172.23.10.249', port='5432', dbname=dbname, user='postgres', password='labpassword')

table_name = 'a_sap_staffing_recruitment_plan_chinese'
sql = f'''
drop table if exists   public.{table_name};
create table public.{table_name}(
编制年度 text null,
编制月度 integer null,
员工子组 text null,
有效编制空缺 integer null,
创建日期 date null,
年度可申请空缺数量 integer null,
季度可申请空缺数量 integer null,
月度可申请空缺数量 integer null,
年度编制数量 integer null,
季度编制数量 integer null,
月度编制数量 integer null,
特批编制数量 integer null,
拟在职人数 integer null,
有效但是没有报到空缺数 integer null,
写入日期 date null,
open数 integer null,
关闭数 integer null,
冻结数 integer null,
集团名称 text null,
一级机构 text null,
二级机构 text null,
三级机构 text null,
职级范围 text null
 );

COMMENT ON TABLE public.{table_name} IS '公司各个部门的招聘计划表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.{table_name}.编制年度 IS '公司的财年，值为"TXXX",其中XXX是数字，例如:["T126","T127","T128"]';
COMMENT ON COLUMN public.{table_name}.编制月度 IS '公司财年中的月度，值有:[1,2,3,4,...,12]';
COMMENT ON COLUMN public.{table_name}.员工子组 IS '员工等级组别，值有["A1","A2","A3","A4","A5"]，其中A5级别最高';
COMMENT ON COLUMN public.{table_name}.一级机构 IS '也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等';
COMMENT ON COLUMN public.{table_name}.二级机构 IS '也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等';
COMMENT ON COLUMN public.{table_name}.三级机构 IS '也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等';


grant select,insert, update, delete on table public.{table_name} to chatgpt;
GRANT ALL PRIVILEGES ON SCHEMA public TO chatgpt;
'''

columns_name_dict = {

    'zyear': '编制年度',
    'zbzyf': '编制月度',
    'persk': '员工子组',
    "zsnum": '有效编制空缺',
    "zczrq": '创建日期',
    "vacyqty": '年度可申请空缺数量',
    "vacqqty": '季度可申请空缺数量',
    "vacmqty": '月度可申请空缺数量',
    "l_vacyqty": '年度编制数量',
    'l_vacqqty': '季度编制数量',
    'l_vacmqty': '月度编制数量',
    "spec_count": '特批编制数量',
    "pa_count": '拟在职人数',
    "vac_count": '有效但是没有报到空缺数',
    "zxrda": '写入日期',
    'zopen': 'open数',
    'zclosed': '关闭数',
    "zfreeze": '冻结数',
    "orgt0": '集团名称',
    "orgt1": '一级机构',
    "orgt2": '二级机构',
    "orgt3": '三级机构',
    'ztrfgr': '职级范围',

}

''' unknow meanings
ZEFSDT,ZSTYP,ZBZJG,ZZPLB,ZCZRQ,ZCZSJ,UNAME,ORGEH,L_VACYQTY,L_VACQQTY,L_VACMQTY,VAC_COUNT,ZOPEN,ZCLOSED,ZFREEZE,ORGH0

'''
for i in columns_name_dict.items():
    sql = sql.replace(i[0], i[1])

# print(sql)
print((dbname+'-'+ table_name).center(80, '='))
print(db.excuSql(sql))

useless_col = ['mandt', 'ztrfgr']

sql = '''
SELECT * FROM hzuser.a_sap_et_zthr_zp_list_ai
    '''
# # 连接数据库的功能初始化
db_oracle = connectOracle()
df = db_oracle.queryOracle(sql)
blob2str = ['ORGT2']
df[blob2str] = df[blob2str].astype(str)

new_columns = [i.lower() for i in df.columns.tolist()]
df.columns = new_columns
# print(df)
df = df.rename(columns=columns_name_dict)

need_col = list(columns_name_dict.values())
df = df[need_col]

fix_colms = ['年度可申请空缺数量', '季度可申请空缺数量', '月度可申请空缺数量']
df[fix_colms] = df[fix_colms].applymap(lambda x: str(x).replace('*', ''))
# df.to_csv('zthr_zp_list.csv',encoding='GBK',index=False)
db.insertGP(df, 'public', table_name)
