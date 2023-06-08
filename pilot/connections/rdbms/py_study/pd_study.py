from pilot.configs.config import Config
import pandas as pd
from sqlalchemy import create_engine, pool
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties
from pyecharts.charts import Bar
from pyecharts import options as opts

CFG = Config()


if __name__ == "__main__":
   # 创建连接池
   engine  = create_engine('mysql+pymysql://root:aa123456@localhost:3306/gpt-user')

   # 从连接池中获取连接


   # 归还连接到连接池中

   # 执行SQL语句并将结果转化为DataFrame
   query = "SELECT * FROM users"
   df = pd.read_sql(query, engine.connect())
   df.style.set_properties(subset=['name'], **{'font-weight': 'bold'})
   # 导出为HTML文件
   with open('report.html', 'w') as f:
      f.write(df.style.render())

   # # 设置中文字体
   # font = FontProperties(fname='SimHei.ttf', size=14)
   #
   # colors = np.random.rand(df.shape[0])
   # df.plot.scatter(x='city', y='user_name', c=colors)
   # plt.show()

   # 查看DataFrame
   print(df.head())


   # 创建数据
   x_data = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
   y_data = [820, 932, 901, 934, 1290, 1330, 1320]

   # 生成图表
   bar = (
      Bar()
         .add_xaxis(x_data)
         .add_yaxis("销售额", y_data)
         .set_global_opts(title_opts=opts.TitleOpts(title="销售额统计"))
   )

   # 生成HTML文件
   bar.render('report.html')
