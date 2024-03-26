# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/25 下午3:17
'''
from db.ConnectMongdb import MyMongdb


def setDatabaseManagerRightUserOrDepart(department, ids=[], mode='add'):
    # 设置管理员权限，输入工号或者_id,
    # department 对应应用的名字
    # mode：add remove
    my = MyMongdb()
    _user_ids = []
    _ids = []
    for id in ids:
        if len(id) < 24:
            _ids.append(id)
        else:
            _user_ids.append(id)
    user_ids = my.userIdGetId(_ids)
    content_list = [str(c['_id']) for c in user_ids]
    content_list.extend(_user_ids)
    print(my.updateDatabaseRight(department, content_list, mode=mode))


if __name__ == '__main__':
    setDatabaseManagerRightUserOrDepart('muplus_chinese', ids=[
        '00137109',
        '00123102',  # huyingcong
        '00168653',  # kimi
        '170036'  # xuhang
    ], mode='add')

    setDatabaseManagerRightUserOrDepart('hr_chinese_dev', ids=[
        '00137109',
        '00007726' # huangwei
    ], mode='add')

    setDatabaseManagerRightUserOrDepart('hr_chinese_fk', ids=[
        '00137109',
        '00108029',  # liaoruizhen
        '00073267',  # jiangling
        '00128870',  # huanglichun
        '00072472',  # linqin
        '00100317',  # chenmeiling
        '00071608',  # lijiamei
        '00144652',  # liuensong
        '00143332',  # liuchunfeng
        '00100495'  # andy
        '00168653'  # kimi
    ], mode='add')
