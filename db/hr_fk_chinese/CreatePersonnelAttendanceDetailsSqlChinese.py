# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/11 上午11:00
'''
from db.ConnectGP import pythonGP
from db.ConnectOracle import connectOracle
import sys
if len(sys.argv)>1:
    dbname = sys.argv[1]
else:
    dbname = 'hr_chinese_fk'
db = pythonGP(host='172.23.10.249', port='5432', dbname=dbname, user='postgres', password='labpassword')

table_name = 'a_sap_employee_attendance_details_chinese'

sql = f'''
drop table if exists public.{table_name};
create table public.{table_name}( 
人员工号    integer       null,    
姓名          text   null,   
雇佣状态    text     null, 
人事范围     text    null,
上班地点    text    null,
考勤日期       date        null,
星期几     text    null,
日工作计划   text    null,
上班1         text    null,
下班1         text    null,            
上班2         text    null,    
下班2         text    null,    
上班3         text    null,    
下班3         text    null,    
上班4         text    null,    
下班4         text    null,    
上班5         text    null,    
下班5         text    null,    
迟到分钟数       integer     null,        
早退分钟数       integer     null, 
迟到早退分钟数      integer     null,       
旷工小时数        integer     null, 
出勤工时             integer     null, 
异常类型        text    null,    
单据类型        text    null,    
冲销时长        text    null,    
原始平时加班       integer     null,        
有效平时加班       integer     null, 
原始周末加班        integer     null,       
有效周末加班        integer     null, 
原始法定加班            integer     null, 
有效法定加班        integer     null, 
实际出勤工时        integer     null, 
三级员工周六（打卡时数）          integer     null, 
班别代码            text    null,    
考勤模式            text    null,    
工资等级组           text    null,   
单据状态            text    null,   
员工子组            text    null,   
隶属小组            text    null,   
原始值班             integer     null, 
有效值班                 integer     null, 
职位              text    null,    
员工子组文本          text    null,    
工作区域            text    null 
 );
COMMENT ON TABLE public.{table_name} IS '公司所有员工每天的考勤表';

-- 为各个字段添加说明
COMMENT ON COLUMN public.{table_name}.单据状态  IS '异常处理的单据的状态，值有：["已审核","未审核"]';
COMMENT ON COLUMN public.{table_name}.日工作计划  IS '当前员工的工作计划，值有：["白班0800-ND","夜班2000","白班0700"...]等等';
COMMENT ON COLUMN public.{table_name}.上班1    IS '员工当天第一次打上班卡的时间';
COMMENT ON COLUMN public.{table_name}.上班2    IS '员工当天第二次打上班卡的时间';
COMMENT ON COLUMN public.{table_name}.上班3    IS '员工当天第三次打上班卡的时间';
COMMENT ON COLUMN public.{table_name}.上班4    IS '员工当天第四次打上班卡的时间';
COMMENT ON COLUMN public.{table_name}.上班5    IS '员工当天第五次打上班卡的时间';
COMMENT ON COLUMN public.{table_name}.下班1    IS '员工当天第一次打下班卡的时间';
COMMENT ON COLUMN public.{table_name}.下班2    IS '员工当天第二次打下班卡的时间';
COMMENT ON COLUMN public.{table_name}.下班3    IS '员工当天第三次打下班卡的时间';
COMMENT ON COLUMN public.{table_name}.下班4    IS '员工当天第四次打下班卡的时间';
COMMENT ON COLUMN public.{table_name}.下班5    IS '员工当天第五次打下班卡的时间';
COMMENT ON COLUMN public.{table_name}.雇佣状态 IS '值为：["在职","离职"]';
COMMENT ON COLUMN public.{table_name}.人员工号 IS '可以用这个字段和其他表的进行关联';
COMMENT ON COLUMN public.{table_name}.考勤模式 IS '值为：["免刷卡人员","一次刷卡人员","两次刷卡人员","四次刷卡人员"]';
COMMENT ON COLUMN public.{table_name}.员工子组文本 IS '值为：["顾问","实习","二级员工","五级员工","一级员工","三级员工","CJR","四级员工"]';
COMMENT ON COLUMN public.{table_name}.员工子组 IS '值为：["B1","B3","A2","A5","A1","A3","B3","A4"]';
COMMENT ON COLUMN public.{table_name}.上班地点 IS '值为：["SSL","SZ(深圳)","WX(无锡)","XM","IN","BM","HK","SG","MNO","ND","SSL-P"]';

grant select,insert, update, delete on table public.{table_name} to chatgpt;
GRANT ALL PRIVILEGES ON SCHEMA public TO chatgpt;
'''
print(sql)
print(db.excuSql(sql))

new_columns_dict = {

    "pernr": "人员工号", "ename": "姓名", "statx": "雇佣状态", "werkt": "人事范围", "anstx": "上班地点", "zdate": "考勤日期", "weekd": "星期几", "rtext": "日工作计划", "f0001": "上班1", "t0001": "下班1", "f0002": "上班2",
    "t0002": "下班2", "f0003": "上班3", "t0003": "下班3", "f0004": "上班4", "t0004": "下班4", "f0005": "上班5", "t0005": "下班5", "zcdsj": "迟到分钟数", "zztsj": "早退分钟数", "zcdzt": "迟到早退分钟数", "zkgsj": "旷工小时数",
    "zcqgs": "出勤工时", "zyclx": "异常类型", "zdjlx": "单据类型", "zcxsc": "冲销时长", "zysps": "原始平时加班", "zyxps": "有效平时加班", "zyszm": "原始周末加班", "zyxzm": "有效周末加班", "zysjr": "原始法定加班", "zyxjr": "有效法定加班",
    "scqgs": "实际出勤工时", "zsjdks": "三级员工周六（打卡时数）", "zbbdm": "班别代码", "t555v_ztext": "考勤模式", "pa0008_trfgr": "工资等级组", "zzt": "单据状态", "persk": "员工子组", "orgtx": "隶属小组", "zyszb": "原始值班",
    "zyxzb": "有效值班", "plant": "职位", "ptext": "员工子组文本", "zgzqy": "工作区域"

}

from datetime import datetime, timedelta

# 获取现在的时间
now = datetime.now()
days = 1
while days < 90:
    # 获取前一天的时间
    yesterday = now - timedelta(days=days)
    print(days,yesterday)
    days+=1

    # 获取前一天的年月日
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    sql = f'''
    SELECT * FROM hzuser.A_SAP_PERSONNEL_ATTENDANCE_DETAILS_AI aspada  WHERE  to_char(ZDATE,'YYYY-MM-DD')='{yesterday_str}'
    '''

    # # 连接数据库的功能初始化
    db_oracle = connectOracle()
    df = db_oracle.queryOracle(sql)
    print(df.shape)
    blob2str = ['ORGTX']
    df[blob2str] = df[blob2str].astype(str)

    new_columns = [i.lower() for i in df.columns.tolist()]
    df.columns = new_columns
    need_columns = new_columns_dict.keys()
    df = df[need_columns]

    df = df.rename(columns=new_columns_dict)
    db.insertGP(df, 'public', table_name)
