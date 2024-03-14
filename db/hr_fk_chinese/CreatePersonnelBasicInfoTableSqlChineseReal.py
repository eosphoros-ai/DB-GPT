# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/11 上午9:03
'''
from db.ConnectGP import pythonGP
import pandas as pd
import json

from db.ConnectOracle import connectOracle

db = pythonGP(host='172.23.10.249', port='5432', dbname='hr_chinese_fk', user='postgres', password='labpassword')

table_name = 'a_sap_employee_information_chinese'
sql = f'''

drop table if exists  public.{table_name} CASCADE;
create table public.{table_name}(

人员工号             integer       PRIMARY KEY,    
姓名                 text   null,   
职级                 text   null,   
雇佣状态              text     null, 
职位                 text     null,
入职日期              date      null,
离职类型              text      null,
离职原因              text      null,
离职日期              date      null,
部门负责人          text    null,    
人事范围            text    null,
员工组             text    null, 
员工子组文本          text    null,
上班地点            text    null,
英文名                text    null,     
性别                text    null,
国籍       text       null,
民族       text       null,
婚姻状况       text       null,
籍贯             text       null,
身份证地址的省_直辖市             text       null,     
开始参加工作日期             date       null, 
员工本人联系号码             text       null,    --too long
一级机构         text     null, 
二级机构         text     null,
三级机构         text     null,
职务名称            text        null,
员工工作性质文本        text        null,
直属上司工号        integer        null,         
直属上司姓名       text        null,        
集团入职日期           date        null,
最近一次晋升日期           date        null

);
COMMENT ON TABLE public.{table_name} IS '公司里所有员工基本信息表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.{table_name}.人员工号 IS '每个员工的唯一工号，也是这张表的主键';
COMMENT ON COLUMN public.{table_name}.雇佣状态 IS '值为：["在职","离职"]';
COMMENT ON COLUMN public.{table_name}.职级 IS '值为：["F1","F2","F3","F4","F5","F6","F7"]';
COMMENT ON COLUMN public.{table_name}.部门负责人 IS '该员工所属部门（一级机构）的负责人姓名';
COMMENT ON COLUMN public.{table_name}.人事范围 IS '值为：["Ampack-DG","SSL","SZ","Poweramp","Ampack","BM","HK","ND","Ampace"]';
COMMENT ON COLUMN public.{table_name}.员工组 IS '值为：["劳务外包","试用","退休返聘","CJR","劳务派遣-正式","正式","劳务派遣-试用","顾问","实习"]';
COMMENT ON COLUMN public.{table_name}.离职类型 IS '值为：["退休","主动辞职","被动辞职","辞退"]';
COMMENT ON COLUMN public.{table_name}.离职原因 IS '值包括：["离职-不计离职率","集团内互转","解除劳动关系"..]等等';
COMMENT ON COLUMN public.{table_name}.员工子组文本 IS '值为：["顾问","实习","二级员工","五级员工","一级员工","三级员工","CJR","四级员工"]';
COMMENT ON COLUMN public.{table_name}.上班地点 IS '值为：["SSL","SZ(深圳)","WX(无锡)","XM","IN","BM","HK","SG","MNO","ND","SSL-P"]';
COMMENT ON COLUMN public.{table_name}.一级机构 IS '也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等';
COMMENT ON COLUMN public.{table_name}.二级机构 IS '也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等';
COMMENT ON COLUMN public.{table_name}.三级机构 IS '也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等';
COMMENT ON COLUMN public.{table_name}.员工工作性质文本 IS '值为：["兼职-不计算","劳务外包","兼职-计算","全职-计算","挂职"]';

grant select,insert, update, delete on table public.{table_name} to chatgpt;
GRANT ALL PRIVILEGES ON SCHEMA public TO chatgpt;
'''
# T529T_ZLZLX	T530T_ZLZYY	PA9022_ZLZMS
rename_dict = {
    "PA0001_PERNR": 'pernr',
    "PA0001_BTRTL": 'btrtl',
    "PA0001_ENAME": 'ename',
    "PA0008_TRFGR": 'pa0008_trfgr',
    "T529U_TEXT": 't529u_text',
    "T502T_FTEXT": 't502t_ftext',
    "PLANS_TEXT": 'plans_text',
    "PA0000_RZDTM": 'rzdtm',
    "PA0001_PERSON_NAME": 'person_name',
    "T529T_ZLZLX": 'zlzlx',
    "T530T_ZLZYY": 'zlzyy',
    "PA0000_LZDTM": 'lzdtm',
    "T500P_NAME1": 't500p_name1',
    "T501T_PTEXT": 't501t_ptext',
    "T503T_PTEXT": 't503t_ptext',
    "T542T_ATX": 't542t_atx',
    "PA0002_RUFNM": 'rufnm',
    "PA0002_GESCH": 'gesch',
    "T005T_NATIO": 't005t_natio',
    "T505S_LTEXT": 't505s_ltext',
    "PA0002_ZJIGU": 'zjigu',
    "PA0006_ZXADD": 'zxadd',
    "PA0022_STEXT": 'stext',
    "PA0022_BYDTM": 'bydtm',
    "PA0022_INSTI": 'insti',
    "PA0022_ZZHYE": 'zzhye',
    "PA0041_DAT01": 'dat01',
    "PA0105_USRID": 'usrid',
    "ORG_TEXT_L1": 'org_text_l1',
    "ORG_TEXT_L2": 'org_text_l2',
    "ORG_TEXT_L3": 'org_text_l3',
    "HRP1000_SHORT": 'hrp1000_short',
    "PA9001_ZGSLX": 'zgslx',
    "PA9001_GSTXT": 'gstxt',
    "OPATHN": 'opathn',
    "STLTX": 'stltx',
    "ZBUSTX": 'zbustx',
    "ZGZXZ_TXT": 'zgzxz_txt',
    "ZZSSJ_NUM": 'zzssj_num',
    "ZZSSJ_NAME": 'zzssj_name',
    "ZZJTRZ": 'zzjtrz',
    "ZJSDAT": 'zjsdat',
}

'''
PA0001_PERNR,PA0001_BTRTL,PA0001_ENAME,PA0008_TRFGR,T529U_TEXT,T502T_FTEXT,PLANS_TEXT,PA0000_RZDTM,PA0001_PERSON_NAME,T529T_ZLZLX,T530T_ZLZYY,PA0000_LZDTM,T500P_NAME1,T501T_PTEXT,T503T_PTEXT,T542T_ATX,PA0002_RUFNM,PA0002_GESCH,T005T_NATIO,T505S_LTEXT,PA0002_ZJIGU,PA0006_ZXADD,PA0022_STEXT,PA0022_BYDTM,PA0022_INSTI,PA0022_ZZHYE,PA0041_DAT01,PA0105_USRID,ORG_TEXT_L1,ORG_TEXT_L2,ORG_TEXT_L3,HRP1000_SHORT,PA9001_ZGSLX,PA9001_GSTXT,OPATHN,STLTX,ZBUSTX,ZGZXZ_TXT,ZZSSJ_NUM,ZZSSJ_NAME,ZZJTRZ,ZJSDAT
'''
#  最终选用字段。
columns_name_dict_new = {
    'pernr': '人员工号',
    'ename': '姓名',
    'pa0008_trfgr': '职级',
    't529u_text': '雇佣状态',
    'plans_text': '职位',
    'rzdtm': '入职日期',
    'zlzlx': '离职类型',
    'zlzyy': '离职原因',
    'lzdtm': '离职日期',
    'person_name': '部门负责人',
    't542t_atx': '上班地点',
    'rufnm': '英文名',
    'gesch': '性别',
    't005t_natio': '国籍',
    't502t_ftext': '婚姻状况',
    't505s_ltext': '民族',
    't500p_name1': '人事范围',
    't501t_ptext': '员工组',
    't503t_ptext': '员工子组文本',
    'zjigu': '籍贯',
    'zxadd': '身份证地址的省_直辖市',
    'dat01': '开始参加工作日期',
    'usrid': '员工本人联系号码',
    'org_text_l1': '一级机构',
    'org_text_l2': '二级机构',
    'org_text_l3': '三级机构',
    'stltx': '职务名称',
    'zgzxz_txt': '员工工作性质文本',
    'zzssj_num': '直属上司工号',
    'zzssj_name': '直属上司姓名',
    'zzjtrz': '集团入职日期',
    'zjsdat': '最近一次晋升日期'
}

for i in columns_name_dict_new.items():
    sql = sql.replace(i[0], i[1])
print(sql)
print(db.excuSql(sql))

useless_col = []
msk_col = ['pernr', 'ename', 'person_name', 'zzssj_name', 'zzssj_num']
phone_number = ['usrid']
int2str = ['pernr', 'zzssj_num']

columns_list  = list(rename_dict.keys())
columns_list.remove('PA0008_TRFGR')
sql = f'''
SELECT     CASE 
        WHEN PA0008_TRFGR IN ('F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7') 
        THEN PA0008_TRFGR 
        ELSE NULL 
    END AS PA0008_TRFGR,{','.join(columns_list)} FROM (SELECT * FROM hzuser.a_sap_personnel_basic_information_ai WHERE PA0008_TRFGR  NOT IN ('C0')   UNION  SELECT * FROM hzuser.a_sap_personnel_basic_information_ai WHERE PA0008_TRFGR IS null ) aa 
    '''
# # 连接数据库的功能初始化
db_oracle = connectOracle()
df = db_oracle.queryOracle(sql)
new_columns = [i.lower() for i in df.columns.tolist()]
df = df.rename(columns=rename_dict)

# df[int2str] = df[int2str].astype(int).astype(str)

df = df.rename(columns=columns_name_dict_new)
need_col = list(columns_name_dict_new.values())

df = df[need_col]
print('data inserting ')
# df.to_csv('personnel_basic_info.csv',encoding='GBK',index=False)
db.insertGP(df, 'public', table_name)
