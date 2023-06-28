from pilot.configs.config import Config
import pandas as pd
from sqlalchemy import create_engine, pool
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties
from pyecharts.charts import Bar
from pyecharts import options as opts
from test_cls_1 import TestBase, Test1
from test_cls_2 import Test2

CFG = Config()

#
# if __name__ == "__main__":
#    # 创建连接池
#    engine  = create_engine('mysql+pymysql://root:aa123456@localhost:3306/gpt-user')
#
#    # 从连接池中获取连接
#
#
#    # 归还连接到连接池中
#
#    # 执行SQL语句并将结果转化为DataFrame
#    query = "SELECT * FROM users"
#    df = pd.read_sql(query, engine.connect())
#    df.style.set_properties(subset=['name'], **{'font-weight': 'bold'})
#    # 导出为HTML文件
#    with open('report.html', 'w') as f:
#       f.write(df.style.render())
#
#    # # 设置中文字体
#    # font = FontProperties(fname='SimHei.ttf', size=14)
#    #
#    # colors = np.random.rand(df.shape[0])
#    # df.plot.scatter(x='city', y='user_name', c=colors)
#    # plt.show()
#
#    # 查看DataFrame
#    print(df.head())
#
#
#    # 创建数据
#    x_data = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
#    y_data = [820, 932, 901, 934, 1290, 1330, 1320]
#
#    # 生成图表
#    bar = (
#       Bar()
#          .add_xaxis(x_data)
#          .add_yaxis("销售额", y_data)
#          .set_global_opts(title_opts=opts.TitleOpts(title="销售额统计"))
#    )
#
#    # 生成HTML文件
#    bar.render('report.html')
#
#


# if __name__ == "__main__":

# def __extract_json(s):
#     i = s.index("{")
#     count = 1  # 当前所在嵌套深度，即还没闭合的'{'个数
#     for j, c in enumerate(s[i + 1 :], start=i + 1):
#         if c == "}":
#             count -= 1
#         elif c == "{":
#             count += 1
#         if count == 0:
#             break
#     assert count == 0  # 检查是否找到最后一个'}'
#     return s[i : j + 1]
#
# ss = """here's a sql statement that can be used to generate a histogram to analyze the distribution of user orders in different cities:select u.city, count(*) as order_countfrom tran_order oleft join user u on o.user_id = u.idgroup by u.city;this will return the number of orders for each city that has at least one order. we can use this data to generate a histogram that shows the distribution of orders across different cities.here's the response in the required format:{ "thoughts": "here's a sql statement that can be used to generate a histogram to analyze the distribution of user orders in different cities:\n\nselect u.city, count(*) as order_count\nfrom tran_order o\nleft join user u on o.user_id = u.id\ngroup by u.city;", "speak": "here's a sql statement that can be used to generate a histogram to analyze the distribution of user orders in different cities.", "command": { "name": "histogram-executor", "args": { "title": "distribution of user orders in different cities", "sql": "select u.city, count(*) as order_count\nfrom tran_order o\nleft join user u on o.user_id = u.id\ngroup by u.city;" } }}"""
# print(__extract_json(ss))

if __name__ == "__main__":
    test1 = Test1()
    test2 = Test2()
    test1.write()
    test1.test()
    test2.write()
    test1.test()
    test2.test()
