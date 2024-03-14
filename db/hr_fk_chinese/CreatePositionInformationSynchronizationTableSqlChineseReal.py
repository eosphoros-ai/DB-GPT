# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/11 上午9:57
'''
from db.ConnectGP import pythonGP
from db.ConnectOracle import connectOracle
import sys
if len(sys.argv)>1:
    dbname = sys.argv[1]
else:
    dbname = 'hr_chinese_fk'
db = pythonGP(host='172.23.10.249', port='5432', dbname=dbname, user='postgres', password='labpassword')

table_name = 'a_sap_positions_responsibilities_risks_chinese'
sql = f'''
drop table if exists public.{table_name};

create table public.{table_name}(
集团 text null,
一级机构 text null,
二级机构 text null,
三级机构 text null,
职位  text null,
成本类别名称   text null,
岗位名称    text null,
岗位属性名称   text null,
角色定位   text null,
岗位风险点   text null,
岗位职责   text null,
岗位任职资格   text null,
绩效贡献   text null,
经验及其他资质要求   text null,
部门职能类型名称   text null,
职务  text null,
职务类型    text null,
现职人数  integer null
);

COMMENT ON TABLE public.{table_name} IS '公司每个岗位的责任和风险表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.{table_name}.一级机构 IS '也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等';
COMMENT ON COLUMN public.{table_name}.二级机构 IS '也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等';
COMMENT ON COLUMN public.{table_name}.三级机构 IS '也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等';
COMMENT ON COLUMN public.{table_name}.成本类别名称 IS '岗位的成本类别，值有：["Mgr.above","IDL","Staff","DL"]';
COMMENT ON COLUMN public.{table_name}.部门职能类型名称 IS '值有：["工程","研发","运营","支持","销售","质量","其它","ATL"]';

COMMENT ON COLUMN public.{table_name}.职务类型 IS '值为：["P1-技术类","F4-文职类","技术类","实习","F2-操作类","P2-非技术类","M-管理类","F3-现场管理类","F1-现场技术类"]';

grant select,insert, update, delete on table public.{table_name} to chatgpt;
GRANT ALL PRIVILEGES ON SCHEMA public TO chatgpt;

'''

columns_name_dict_new = {'zorgeh0': "集团ID", 'zorgeh_txt0': "集团", 'zorgeh1': "一级机构ID", 'zorgeh_txt1': "一级机", 'zorgeh2': "二级机构ID", 'zorgeh_txt2': "二级机构", 'zorgeh3': "三级机构ID", 'zorgeh_txt3': "三级机构",
                         'zorgeh4': "四级机构ID", 'zorgeh_txt4': "四级机构", 'zorgeh5': "五级机构ID", 'zorgeh_txt5': "五级机构", 'zorgeh6': "六级机构ID", 'zorgeh_txt6': "六级机构", 'zorgeh7': "七级机构ID", 'zorgeh_txt7': "七级机构",
                         'zorgeh8': "八级机构ID", 'zorgeh_txt8': "八级机构", 'zorgeh9': "九级机构ID", 'zorgeh_txt9': "九级机构", 'zorgeh10': "十级机构ID", 'zorgeh_txt10': "十级机构", 'plans': "职位ID", 'zplans_txt': "职位",
                         'zcblb': "成本类别", 'zcblb_txt': "成本类别名称", 'zjobid': "岗位编码", 'zjobname': "岗位名称", 'zgwsx': "岗位属", 'zgwsx_txt': "岗位属性名", 'z0001': "角色定位", 'z0002': "岗位风险", 'z0003': "岗位职责",
                         'z0004': "岗位任职资格", 'z0005': "绩效贡献", 'z0007': "经验及其他资质要", 'zbmzn': "部门职能类型", 'zbmzn_txt': "部门职能类型名称", 'stell': "职务ID", 'zstell_txt': "职务", 'zstell_short': "职务类型",
                         'zonnum': "现职人数",

                         }

columns_name_dict = {'zorgeh_txt0': '集团',
                     'zorgeh_txt1': '一级机构',
                     'zorgeh_txt2': '二级机构',
                     'zorgeh_txt3': '三级机构',
                     'zplans_txt': '职位',
                     # 'zcblb': '成本类别',
                     'zcblb_txt': '成本类别名称',
                     'zjobname': '岗位名称',
                     'zgwsx_txt': '岗位属性名称',
                     'z0001': '角色定位',
                     'z0002': '岗位风险点',
                     'z0003': '岗位职责',
                     'z0004': '岗位任职资格',
                     'z0005': '绩效贡献',
                     'z0007': '经验及其他资质要求',
                     'zbmzn_txt': '部门职能类型名称',
                     'zstell_txt': '职务',
                     'zstell_short': '职务类型',
                     'zonnum': '现职人数'}

aa = [j for j in columns_name_dict.items()]

for i in aa[::-1]:
    sql = sql.lower().replace(i[0],
                              i[1])
print(sql)
print(db.excuSql(sql))

useless_col = ['etl_date', 'zrntnum', 'z0006', 'iskeyjob', 'zrnnum', 'zrfnum']
msk_col = []

sql = '''
SELECT * FROM hzuser.a_sap_position_information_synchronization_ai
    '''
# # 连接数据库的功能初始化
db_oracle = connectOracle()
df = db_oracle.queryOracle(sql)
blob2str = ['Z0003']
df[blob2str] = df[blob2str].astype(str)
new_columns = [i.lower() for i in df.columns.tolist()]
df.columns = new_columns

df = df.rename(columns=columns_name_dict)
need_col = list(columns_name_dict.values())
df = df[need_col]
# df = df.drop(useless_col,axis=1)
print(df)
db.insertGP(df, 'public', table_name)
