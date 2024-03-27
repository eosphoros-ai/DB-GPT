# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2023/9/25 15:22
'''
import cx_Oracle
import oracledb
import os

from pathlib import Path
import pandas as pd
from configs.OracleConfig import oracle_host, oracle_port, oracle_database, oracle_user, oracle_password
from utils.Tools import calLeadTimeByColor
import platform

if platform.platform().startswith('Windows'):
    oracledb_file = os.path.join(Path(__file__).parent.parent, 'instantclient_21_12_windows')
else:
    oracledb_file = os.path.join(Path(__file__).parent.parent, 'instantclient_21_11')

';LD_LIBRARY_PATH=/datas/liab/DB-GPT/instantclient_21_11'
oracledb.init_oracle_client(oracledb_file)


class connectOracle(object):
    '''
        Python与oracle建立链接。
    用法：

    '''

    def __init__(self, host=oracle_host, port=oracle_port, dbname=oracle_database, user=oracle_user,
                 password=oracle_password):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password

    def configureOracle(self):
        self.conn = cx_Oracle.connect(self.user, self.password, '{}:{}/{}'.format(self.host, self.port, self.dbname))
        self.cur = self.conn.cursor()

        print('连接Oracle成功。')

        return True

    @calLeadTimeByColor(color=35)
    def queryOracle(self, sql):
        self.configureOracle()
        data = pd.read_sql(sql, self.conn)
        return data

    def closeOracle(self):
        """
            关闭连接
        """
        self.cur.close()

'''
SELECT * FROM hzuser.a_sap_personnel_basic_information_ai WHERE rownum<=10 ORDER BY ZZJTRZ DESC ;
SELECT * FROM hzuser.a_sap_employee_education_information_ai;
SELECT * FROM hzuser.a_sap_reporting_relationship_ai;
SELECT * FROM hzuser.a_sap_personnel_basic_information_ai;
SELECT * FROM hzuser.a_sap_et_zthr_strength_ai;
SELECT * FROM hzuser.a_sap_et_zthr_zp_list_ai;
SELECT * FROM hzuser.a_sap_position_information_synchronization_ai;
'''
if __name__ == '__main__':
    sql = '''
    SELECT * FROM hzuser.a_sap_personnel_basic_information_ai WHERE rownum<=10 ORDER BY ZZJTRZ DESC 
        '''
    # dwd_qs_qm_orig_coa_inspection_df
    # # 连接数据库的功能初始化
    db_oracle = connectOracle()
    data = db_oracle.queryOracle(sql)
    # print(data)

    sql = '''
SELECT 
PRODUCTNO as "成品编码",
CUSTOMCODE  as "客户",
MFPLATFORM as "制造平台",
OPERATIONNO as "工序名称",
OPERATIONNAME as "工序编码",
CHARACTERISTIC as "参数编码",
CHARACTERISTICDESC as "参数",

REPLACE(SAMPLE_QTY_P1,'///',null ) as "过程1频率/抽样数量",
REPLACE(SAMPLE_QTY_P2,'///',null )  as "过程2频率/抽样数量",
REPLACE(SAMPLE_QTY_FIRST,'///',null ) as "首件抽样数量",
--DUTYDEPARTMENT as "责任部门",
CASE
WHEN DUTYDEPARTMENT_P1 IS NOT NULL  THEN DUTYDEPARTMENT_P1 || '/'
ELSE '/'
END ||
CASE
WHEN DUTYDEPARTMENT_P2 IS NOT NULL THEN DUTYDEPARTMENT_P2 || '/'
ELSE '/'
END ||
CASE
WHEN DUTYDEPARTMENT_FIRST IS NOT NULL  THEN DUTYDEPARTMENT_FIRST 
ELSE ''
END AS concatenated_column as "责任部门"
FROM hzuser.A_IPS_BOPSAMPLE_ST WHERE SAMPLE_QTY_P2 IS NOT NULL  OR SAMPLE_QTY_P1 IS NOT NULL  OR SAMPLE_QTY_FIRST IS NOT NULL 

FETCH FIRST 1000 ROWS ONLY

    '''


    print('sql 查询完成')

