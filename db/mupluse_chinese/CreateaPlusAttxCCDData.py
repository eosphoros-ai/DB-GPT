# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/11 上午9:51
'''

from db.ConnectGP import pythonGP
import sys

if len(sys.argv) > 1:
    dbname = sys.argv[1]
else:
    dbname = 'muplus_chinese'
db = pythonGP(host='172.23.10.249', port='5432', dbname=dbname, user='postgres', password='labpassword')

table_name = 'a_sap_plus_attx_ccd_data_chinese'
sql = f'''
drop table if exists   public.{table_name};
CREATE TABLE public.{table_name}(
设备名称 text NULL,     
设备坐标 text NULL, 
时间 date NULL, 
条码 text NULL,
检测结果 text NULL,
ng信息 text NULL,     
电芯长度 text NULL,
电芯宽度 text NULL,
铝边距 text NULL,
铝偏角 text NULL,
镍边距 text NULL,
镍偏角 text NULL,
铝边距2 text NULL,
铝偏角2 text NULL,
阴极长度 text NULL,
阳极长度 text NULL,
中心距 text NULL,
工号 text NULL,
班次 text NULL,
成品编码 text NULL,
料盘编码 text NULL
);

COMMENT ON TABLE public.{table_name} IS 'PLUS绕胶机CCD数据';

COMMENT ON COLUMN public.{table_name}.检测结果 IS '值为：["OK","NG"]';


grant select,insert, update, delete on table public.{table_name} to chatgpt;
GRANT ALL PRIVILEGES ON SCHEMA public TO chatgpt;
'''

columns_name_dict = {
    'EQUIPMENT': '设备名称',
    'EQUIPMENTLOCATION': '设备坐标',
    'DATETIME': '时间',
    'BARCODE': '条码',
    'TESTATTRIBUTE': '检测结果',
    'NGINFORMATION': 'ng信息',
    'CELLLENGTH': '电芯长度',
    'CELLWIDTH': '电芯宽度',
    'ALTABDISTANCE': '铝边距',
    'ALANGLE': '铝偏角',
    'NITABDISTANCE': '镍边距',
    'NIANGLE': '镍偏角',
    'ALTABDISTANCE2': '铝边距2',
    'ALANGLE2': '铝偏角2',
    'CALENGTH': '阴极长度',
    'ANLENGTH': '阳极长度',
    'CENTERDISTANCE': '中心距',
    'JOBID': '工号',
    'SHIFT': '班次',
    'PRODUCTCODE': '成品编码',
    'TRAYCODE': '料盘编码',

}

# print(sql)
print((dbname+'-'+ table_name).center(80, '='))
# print(db.excuSql(sql))

from datetime import datetime, timedelta

# 获取现在的时间
now = datetime.now()
days = 1
while days < 2:
    # 获取前一天的时间
    yesterday = now - timedelta(days=days)
    print(days,yesterday)
    days+=1

    # 获取前一天的年月日
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    sql = f'''
    SELECT * FROM public.plus_attxccddata_table WHERE  to_char(datetime,'YYYY-MM-DD')='{yesterday_str}'
        '''
    # # 连接数据库的功能初始化
    db_oracle = pythonGP(host='172.23.52.12', port='5432', dbname='atldigital', user='cwxadmin', password='cwxadmin')
    df = db_oracle.queryGP(sql)

    new_columns = [i.upper() for i in df.columns.tolist()]
    df.columns = new_columns
    print(df.shape)
    df = df.rename(columns=columns_name_dict)

    need_col = list(columns_name_dict.values())
    df = df[need_col]

    db.insertGP(df, 'public', table_name)
