# -*- encoding:utf-8 -*-
'''
@describe: 一些小工具
@author: Li Anbang
@Create Date: 2022/12/9 14:31
'''
import time

# 字体颜色
'''
-------------------------------------------
字体色     |       背景色     |      颜色描述
-------------------------------------------
30        |        40       |       黑色
31        |        41       |       红色
32        |        42       |       绿色
33        |        43       |       黃色
34        |        44       |       蓝色
35        |        45       |       紫红色
36        |        46       |       青蓝色
37        |        47       |       白色
-------------------------------------------
-------------------------------
显示方式     |      效果
-------------------------------
0           |     终端默认设置
1           |     高亮显示
4           |     使用下划线
5           |     闪烁
7           |     反白显示
8           |     不可见
-------------------------------
'''

def calLeadTimeByColor(color=35):
    def calProcessLeadTime(func):
        # 装饰器，用于修改字段。
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            spend_time = end_time - start_time
            print(f'\033[{color}m [INFO] 运行时间：%.4f !\033[0m' % spend_time)
            return result

        return wrapper
    return calProcessLeadTime


@calLeadTimeByColor(color=33)
def f1():
    time.sleep(1)


if __name__ == '__main__':
    f1()
