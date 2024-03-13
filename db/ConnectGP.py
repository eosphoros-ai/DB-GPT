#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2022/12/9 10:13
# @Author  : LuPeng
# @File    : ConnectGP.py
# @Software: PyCharm
import traceback

import psycopg2
import time
import pandas as pd
gp_host = '172.23.10.250'
gp_port = '5432'
gp_database = 'hr'
gp_user = 'chatgpt'
gp_password = 'chatgpt'

def calProcessLeadTime(func):
    import time
    # 装饰器，用于修改字段。
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        spend_time = end_time - start_time
        print('\033[35m [INFO] 运行时间：%.4f !\033[0m' % spend_time)
        return result

    return wrapper

from sqlalchemy import create_engine
from datetime import date, timedelta, datetime, time

class pythonGP(object):
    '''
        Python与GP建立链接。
    用法：
    # 导入模块
    from db.ConnectGP import pythonGP

    # 实例化
    db = pythonGP()   # 或：db = pythonGP(gp_host, gp_port, gp_database, gp_user, gp_password)

    # 读取数据
    df = db.queryGP(sql)   df = db.queryGP('select * FROM dm.lims_ort_az_model_train_output_df')

    # 插入数据
    db.insertGP(df, schema, table_name) 例子： db.insertGP(df=data, schema='dm', table_name='lims_ort_az_model_train_output_df')

    # 清空数据
    truncateTableGP(self,schema_table_name)
    '''

    def __init__(self, host=gp_host, port=gp_port, dbname=gp_database, user=gp_user, password=gp_password):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password  # self.configureGP()

    def configureGP(self):
        self.connGP = psycopg2.connect(host=self.host, port=self.port, dbname=self.dbname, user=self.user, password=self.password)
        self.connGP.autocommit = True
        self.curGP = self.connGP.cursor()

        return True

    @calProcessLeadTime
    def queryGP(self, sql):
        self.configureGP()
        result = pd.read_sql(sql=sql, con=self.connGP)
        self.closeGP()
        return result

    @calProcessLeadTime
    def queryIterGP(self, sql,**kwargs):
        self.configureGP()
        result = pd.read_sql(sql=sql, con=self.connGP,**kwargs)
        return result



    def excuSql(self, sql):
        self.configureGP()
        res = self.curGP.execute(sql)
        self.closeGP()
        return res

    @calProcessLeadTime
    def insertGP(self, df, schema, table_name):
        """
        :param df: dataframe数据
        :param schema: schema
        :param table_name: 表名
        :return: True
        """
        self.conn_GP = create_engine("postgresql+psycopg2://{}:{}@{}:{}/{}".format(self.user, self.password, self.host, self.port, self.dbname))
        # conn_GP = create_engine("postgresql+psycopg2://{}:{}@{}:{}/{}".format(gp_user, gp_password, gp_host, gp_port, gp_database))

        try:
            df.to_sql(schema=schema, name=table_name, con=self.conn_GP, if_exists="append", index=False)
            # 另一种方法
            # pd.io.sql.to_sql(df, name=table_name, con=self.conn_GP, index=False, schema=schema, if_exists='append')
            print('插入成功'.center(40, '*'))
            # 销毁连接,彻底关闭
            self.conn_GP.dispose()
            return True

        except Exception as error:
            print(traceback.print_exc())
            print('插入失败'.center(40, '*'))

            return False
    @calProcessLeadTime
    def insertIterGP(self, df, schema, table_name):
        """
        :param df: dataframe数据
        :param schema: schema
        :param table_name: 表名
        :return: True
        """
        self.conn_GP = create_engine("postgresql+psycopg2://{}:{}@{}:{}/{}".format(self.user, self.password, self.host, self.port, self.dbname))
        # conn_GP = create_engine("postgresql+psycopg2://{}:{}@{}:{}/{}".format(gp_user, gp_password, gp_host, gp_port, gp_database))

        try:
            df.to_sql(schema=schema, name=table_name, con=self.conn_GP, if_exists="append", index=False)
            # 另一种方法
            # pd.io.sql.to_sql(df, name=table_name, con=self.conn_GP, index=False, schema=schema, if_exists='append')
            print('插入成功'.center(40, '*'))
            # 销毁连接,彻底关闭
            return True

        except Exception as error:
            print(traceback.print_exc())
            print('插入失败'.center(40, '*'))

            return False

    def truncateTableGP(self, schema_table_name):
        """
            清空表
        :param schema_table_name: 清空的"schema.表名"
        """
        self.configureGP()
        sql = 'TRUNCATE TABLE {} RESTART IDENTITY'.format(schema_table_name)
        self.curGP.execute(sql)
        print('成功清空表：{}'.format(schema_table_name).center(40, '*'))
        self.closeGP()

    def closeGP(self):
        """
            关闭连接
        """
        self.curGP.close()
        self.connGP.close()



if __name__ == '__main__':
    pass
    db = pythonGP(host='172.19.135.72', port='5432', dbname='postgres', user='chatgpt', password='chatgpt')
    # print(db.queryGP('select * from  dm.lims_ask_static_info limit 100'))

