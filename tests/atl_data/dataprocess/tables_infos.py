# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/1/10 下午1:54
'''
tables_schema = '''
-- 公司招聘编制使用情况表create table public.a_sap_staffing_recruitment_plan_chinese(
编制年度 varchar(40) null,
编制月度 integer null,
员工子组 varchar(40) null,
有效编制空缺 integer null,
创建日期 date null,
年度可申请空缺数量 integer null,
季度可申请空缺数量 integer null,
月度可申请空缺数量 integer null,
年度编制数量 integer null,
季度编制数量 integer null,
月度编制数量 integer null,
特批编制数量 integer null,
拟在职人数 integer null,
有效但是没有报到空缺数 integer null,
写入日期 date null,
open数 integer null,
关闭数 integer null,
冻结数 integer null,
集团名称 varchar(40) null,
一级机构 varchar(40) null,
二级机构 varchar(40) null,
三级机构 varchar(40) null,
职级范围 varchar(40) null
 );

COMMENT ON TABLE public.a_sap_staffing_recruitment_plan_chinese IS '这个是公司各个部门（一级机构），小组（二级机构、三级机构），在每个编制年度(财年)/编制月度的招聘计划表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.a_sap_staffing_recruitment_plan_chinese.编制年度 IS '公司的财年，值为"TXXX",其中XXX是数字，例如:["T126","T127","T128"]';
COMMENT ON COLUMN public.a_sap_staffing_recruitment_plan_chinese.编制月度 IS '公司财年中的月度，值有:[1,2,3,4,...,12]';
COMMENT ON COLUMN public.a_sap_staffing_recruitment_plan_chinese.员工子组 IS '员工等级组别，值有["A1","A2","A3","A4","A5"]，其中A5级别最高';
COMMENT ON COLUMN public.a_sap_staffing_recruitment_plan_chinese.一级机构 IS '也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等';
COMMENT ON COLUMN public.a_sap_staffing_recruitment_plan_chinese.二级机构 IS '也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等';
COMMENT ON COLUMN public.a_sap_staffing_recruitment_plan_chinese.三级机构 IS '也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等';

----------------------------------------------------------------------------------------------------

-- 员工教育信息表
create table public.a_sap_employee_education_experience_chinese(

人员工号 integer PRIMARY KEY,     
姓名  varchar(20) null , 
开始日期  date null, 
结束日期  date null,
学历  varchar(40) null,
教育类型  varchar(40) null,     
院校_培训机构  varchar(200) null,
国家  varchar(40) null,
证书  varchar(40) null,
第一专业  varchar(200) null,
CONSTRAINT fk_education_basic_info
  FOREIGN KEY(人员工号) 
  REFERENCES a_sap_employee_information_chinese(人员工号)
  ON UPDATE CASCADE 
  ON DELETE CASCADE
);

COMMENT ON TABLE public.a_sap_employee_education_experience_chinese IS '这个是公司每个员工受教育经历的数据表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.a_sap_employee_education_experience_chinese.人员工号 IS '每个员工的唯一工号，也是这张表的主键';
COMMENT ON COLUMN public.a_sap_employee_education_experience_chinese.开始日期 IS '受教育的开始日期';
COMMENT ON COLUMN public.a_sap_employee_education_experience_chinese.结束日期 IS '受教育的结束日期';
COMMENT ON COLUMN public.a_sap_employee_education_experience_chinese.学历 IS '值：["硕士","高中","大学专科","博士","初中及以下","大学本科","中专"]';

---------------------------------------------------------------------------------------------------- 

-- 员工基础信息表
create table public.a_sap_employee_information_chinese(

人员工号             integer       PRIMARY KEY,    
姓名                 varchar(50)   null,   
雇佣状态              varchar(30)     null, 
职位                 varchar(100)     null,
入职日期              date      null,
部门负责人          varchar(50)    null,    
人事范围            varchar(30)    null,
员工组             varchar(30)    null, 
员工子组文本          varchar(30)    null,
上班地点            varchar(30)    null,
英文名                varchar(50)    null,     
性别                varchar(30)    null,
国籍       varchar(30)       null,
民族       varchar(30)       null,
籍贯             varchar(100)       null,
身份证地址的省_直辖市             varchar(30)       null,     
开始参加工作日期             date       null, 
员工本人联系号码             varchar(30)       null,    
一级机构         varchar(30)     null, 
二级机构         varchar(30)     null,
三级机构         varchar(30)     null,
职务名称            varchar(30)        null,
员工工作性质文本        varchar(30)        null,
直属上司工号        integer        null,         
直属上司姓名       varchar(30)        null,        
集团入职日期           date        null

);
COMMENT ON TABLE public.a_sap_employee_information_chinese IS '这个是公司每个员工基本信息表。';

-- 为各个字段添加说明
COMMENT ON COLUMN public.a_sap_employee_information_chinese.人员工号 IS '每个员工的唯一工号，也是这张表的主键';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.雇佣状态 IS '值为：["在职","离职"]';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.部门负责人 IS '该员工所属部门（一级机构）的负责人姓名';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.人事范围 IS '值为：["Ampack-DG","SSL","SZ","Poweramp","Ampack","BM","HK","ND","Ampace"]';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.员工组 IS '值为：["劳务外包","试用","退休返聘","CJR","劳务派遣-正式","正式","劳务派遣-试用","顾问","实习"]';

COMMENT ON COLUMN public.a_sap_employee_information_chinese.员工子组文本 IS '值为：["顾问","实习","二级员工","五级员工","一级员工","三级员工","CJR","四级员工"]';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.上班地点 IS '值为：["SSL","SZ(深圳)","WX(无锡)","XM","IN","BM","HK","SG","MNO","ND","SSL-P"]';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.一级机构 IS '也称为部门，值一般为英文字母组成，例如：["IDT","APD","HR","QA","FE"]等';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.二级机构 IS '也称为组，是部门下分组，例如：["AI","AD","CPA","TA"]等等';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.三级机构 IS '也称为组，是二级机构下面的更细分的小组，例如：["EMC","IPQC","PH","EP-M"]等等';
COMMENT ON COLUMN public.a_sap_employee_information_chinese.员工工作性质文本 IS '值为：["兼职-不计算","劳务外包","兼职-计算","全职-计算","挂职"]'; 

----------------------------------------------------------------------------------------------------

-- 企业机构和岗位需求明细表
create table public.a_sap_positions_responsibilities_risks_chinese(
集团 varchar(40) null,
一级机构 varchar(40) null,
二级机构 varchar(40) null,
三级机构 varchar(40) null,
职位  varchar(60) null,
成本类别名称   varchar(40) null,
岗位名称    varchar(40) null,
岗位属性名称   varchar(70) null,
角色定位   text null,
岗位风险点   text null,
岗位职责   text null,
岗位任职资格   text null,
绩效贡献   text null,
经验及其他资质要求   text null,
部门职能类型名称   varchar(40) null,
职务  varchar(40) null,
职务类型    varchar(60) null,
现职人数  integer null
);

comment on table public.a_sap_positions_responsibilities_risks_chinese is '这个是公司每个岗位的责任和风险，以及绩效贡献标准等等表。';

-- 为各个字段添加说明
comment on column public.a_sap_positions_responsibilities_risks_chinese.一级机构 is '也称为部门，值一般为英文字母组成，例如：["idt","apd","hr","qa","fe"]等';
comment on column public.a_sap_positions_responsibilities_risks_chinese.二级机构 is '也称为组，是部门下分组，例如：["ai","ad","cpa","ta"]等等';
comment on column public.a_sap_positions_responsibilities_risks_chinese.三级机构 is '也称为组，是二级机构下面的更细分的小组，例如：["emc","ipqc","ph","ep-m"]等等';
comment on column public.a_sap_positions_responsibilities_risks_chinese.成本类别名称 is '岗位的成本类别，值有：["mgr.above","idl","staff","dl"]';
comment on column public.a_sap_positions_responsibilities_risks_chinese.部门职能类型名称 is '值有：["工程","研发","运营","支持","销售","质量","其它","atl"]';
comment on column public.a_sap_positions_responsibilities_risks_chinese.职务类型 is '值为：["p1-技术类","f4-文职类","技术类","实习","f2-操作类","p2-非技术类","m-管理类","f3-现场管理类","f1-现场技术类"]';

----------------------------------------------------------------------------------------------------

-- 员工汇报关系表
create table public.a_sap_reporting_relationship_chinese(
开始日期  date null,
结束日期  date null,           
人员工号  integer primary key,   
姓名  varchar(60) null,
入司日期  date null,
工作性质  varchar(40) null,
一级机构  varchar(40) null,
二级机构  varchar(40) null,
三级机构  varchar(40) null,
是否管理机构  varchar(40) null,
主管1姓名  varchar(40) null,
主管1职位  varchar(100) null,
主管1职务  varchar(40) null,
主管2姓名  varchar(40) null, 
主管2职位  varchar(1000) null,
主管2职务  varchar(40) null,
经理1姓名  varchar(40) null,
经理1职位  varchar(100) null,
经理1职务  varchar(40) null,
经理2姓名  varchar(40) null,
经理2职位  varchar(100) null,
经理2职务  varchar(40) null,
经理3姓名  varchar(40) null,
经理3职位  varchar(100) null,
经理3职务  varchar(40) null,
经理4姓名  varchar(40) null,
经理4职位  varchar(100) null,
经理4职务  varchar(40) null,
总监1姓名  varchar(40) null,
总监1职位  varchar(100) null,
总监1职务  varchar(40) null,
总监2姓名  varchar(40) null,
总监2职位  varchar(100) null,
总监2职务  varchar(40) null,
总监3姓名  varchar(40) null,
总监3职位  varchar(100) null,
总监3职务  varchar(40) null,
总监4姓名  varchar(40) null,
总监4职位  varchar(100) null,
总监4职务  varchar(40) null,
一级机构负责人姓名  varchar(40) null,
一级机构负责人职位  varchar(100) null,
一级机构负责人职务  varchar(40) null,
constraint fk_report_basic_info
  foreign key(人员工号) 
  references a_sap_employee_information_chinese(人员工号)
  on update cascade 
  on delete cascade
);

comment on table public.a_sap_reporting_relationship_chinese is '这个是公司每个员工汇报关系表。';

-- 为各个字段添加说明
comment on column public.a_sap_reporting_relationship_chinese.开始日期 is '汇报关系开始的时间';
comment on column public.a_sap_reporting_relationship_chinese.结束日期 is '汇报关系结束的时间';
comment on column public.a_sap_reporting_relationship_chinese.人员工号 is '该表主键，每个员工的唯一id值。';
comment on column public.a_sap_reporting_relationship_chinese.工作性质 is '值为：["全职-计算","挂职","兼职-不计算","劳务外包"]';

comment on column public.a_sap_reporting_relationship_chinese.一级机构 is '也称为部门，值一般为英文字母组成，例如：["idt","apd","hr","qa","fe"]等';
comment on column public.a_sap_reporting_relationship_chinese.二级机构 is '也称为组，是部门下分组，例如：["ai","ad","cpa","ta"]等等';
comment on column public.a_sap_reporting_relationship_chinese.三级机构 is '也称为组，是二级机构下面的更细分的小组，例如：["emc","ipqc","ph","ep-m"]等等';
comment on column public.a_sap_reporting_relationship_chinese.是否管理机构 is '该员工是否是部门（一级机构），小组（二级机构，三级机构）负责人。值为：["是","否"]';
----------------------------------------------------------------------------------------------------

--员工绩效表
create table public.a_sap_performance_ai( 
编制年度 varchar(20) null,
姓名 varchar(40) null,
人员工号 integer null,
绩效 varchar(10) null
 );
COMMENT ON TABLE public.a_sap_performance_ai IS '这个是公司每个员工每个财年的绩效表';

-- 为各个字段添加说明
COMMENT ON COLUMN public.a_sap_performance_ai.编制年度 IS '公司财年';
COMMENT ON COLUMN public.a_sap_performance_ai.绩效 IS '绩效排序（好->差）:["A","B+","B","B-","C","D"]';

--员工考勤表
create table public.a_sap_employee_attendance_details_ai( 
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
COMMENT ON TABLE public.a_sap_employee_attendance_details_ai IS '公司所有员工每天的考勤表';

-- 为各个字段添加说明
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.单据状态  IS '异常处理的单据的状态，值有：["已审核","未审核"]';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.日工作计划  IS '当前员工的工作计划，值有：["白班0800-ND","夜班2000","白班0700"...]等等';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.上班1    IS '员工当天第一次打上班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.上班2    IS '员工当天第二次打上班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.上班3    IS '员工当天第三次打上班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.上班4    IS '员工当天第四次打上班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.上班5    IS '员工当天第五次打上班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.下班1    IS '员工当天第一次打下班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.下班2    IS '员工当天第二次打下班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.下班3    IS '员工当天第三次打下班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.下班4    IS '员工当天第四次打下班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.下班5    IS '员工当天第五次打下班卡的时间';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.雇佣状态 IS '值为：["在职","离职"]';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.人员工号 IS '可以用这个字段和其他表的进行关联';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.考勤模式 IS '值为：["免刷卡人员","一次刷卡人员","两次刷卡人员","四次刷卡人员"]';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.员工子组文本 IS '值为：["顾问","实习","二级员工","五级员工","一级员工","三级员工","CJR","四级员工"]';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.员工子组 IS '值为：["B1","B3","A2","A5","A1","A3","B3","A4"]';
COMMENT ON COLUMN public.a_sap_employee_attendance_details_ai.上班地点 IS '值为：["SSL","SZ(深圳)","WX(无锡)","XM","IN","BM","HK","SG","MNO","ND","SSL-P"]';

'''

columns_table_map = {
    '编制年度': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '编制月度': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '员工子组': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '有效编制空缺': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '创建日期': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '年度可申请空缺数量': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '季度可申请空缺数量': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '月度可申请空缺数量': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '年度编制数量': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '季度编制数量': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '月度编制数量': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '特批编制数量': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '拟在职人数': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '有效但是没有报到空缺数': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '写入日期': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    'open数': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '关闭数': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '冻结数': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '集团名称': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '职级范围': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '人员工号': 'a_sap_employee_education_information_ai_chinese_real',
    '学历': 'a_sap_employee_education_information_ai_chinese_real',
    '教育类型': 'a_sap_employee_education_information_ai_chinese_real',
    '院校_培训机构': 'a_sap_employee_education_information_ai_chinese_real',
    '国家': 'a_sap_employee_education_information_ai_chinese_real',
    '证书': 'a_sap_employee_education_information_ai_chinese_real',
    '第一专业': 'a_sap_employee_education_information_ai_chinese_real',
    '人员编号': 'a_sap_personnel_basic_information_ai_chinese_real',
    '雇佣状态': 'a_sap_personnel_basic_information_ai_chinese_real',
    '入职日期': 'a_sap_personnel_basic_information_ai_chinese_real',
    '部门负责人': 'a_sap_personnel_basic_information_ai_chinese_real',
    '人事范围': 'a_sap_personnel_basic_information_ai_chinese_real',
    '员工组': 'a_sap_personnel_basic_information_ai_chinese_real',
    '员工子组文本': 'a_sap_personnel_basic_information_ai_chinese_real',
    '上班地点': 'a_sap_personnel_basic_information_ai_chinese_real',
    '英文名': 'a_sap_personnel_basic_information_ai_chinese_real',
    '性别': 'a_sap_personnel_basic_information_ai_chinese_real',
    '国籍': 'a_sap_personnel_basic_information_ai_chinese_real',
    '民族': 'a_sap_personnel_basic_information_ai_chinese_real',
    '籍贯': 'a_sap_personnel_basic_information_ai_chinese_real',
    '身份证地址的省_直辖市': 'a_sap_personnel_basic_information_ai_chinese_real',
    '开始参加工作日期': 'a_sap_personnel_basic_information_ai_chinese_real',
    '员工本人联系号码': 'a_sap_personnel_basic_information_ai_chinese_real',
    '一级机构名称': 'a_sap_personnel_basic_information_ai_chinese_real',
    '二级机构名称': 'a_sap_personnel_basic_information_ai_chinese_real',
    '三级机构名称': 'a_sap_personnel_basic_information_ai_chinese_real',
    '职务名称': ['a_sap_personnel_basic_information_ai_chinese_real', 'a_sap_reporting_relationship_ai_chinese_real'],
    '员工工作性质文本': 'a_sap_personnel_basic_information_ai_chinese_real',
    '直属上司工号': 'a_sap_personnel_basic_information_ai_chinese_real',
    '直属上司姓名': 'a_sap_personnel_basic_information_ai_chinese_real',
    '集团': 'a_sap_position_information_synchronization_ai_chinese_real',
    '一级机构': ['a_sap_position_information_synchronization_ai_chinese_real',
                 'a_sap_reporting_relationship_ai_chinese_real', 'a_sap_et_zthr_zp_list_ai_chinese_real'],
    '二级机构': ['a_sap_position_information_synchronization_ai_chinese_real',
                 'a_sap_reporting_relationship_ai_chinese_real', 'a_sap_et_zthr_zp_list_ai_chinese_real'],
    '三级机构': ['a_sap_position_information_synchronization_ai_chinese_real',
                 'a_sap_reporting_relationship_ai_chinese_real', 'a_sap_et_zthr_zp_list_ai_chinese_real'],
    '职位': ['a_sap_position_information_synchronization_ai_chinese_real',
             'a_sap_reporting_relationship_ai_chinese_real', 'a_sap_personnel_basic_information_ai_chinese_real'],
    '成本类别名称': 'a_sap_position_information_synchronization_ai_chinese_real',
    '岗位名称': 'a_sap_position_information_synchronization_ai_chinese_real',
    '岗位属性名称': 'a_sap_position_information_synchronization_ai_chinese_real',
    '角色定位': 'a_sap_position_information_synchronization_ai_chinese_real',
    '岗位风险点': 'a_sap_position_information_synchronization_ai_chinese_real',
    '岗位职责': 'a_sap_position_information_synchronization_ai_chinese_real',
    '岗位任职资格': 'a_sap_position_information_synchronization_ai_chinese_real',
    '绩效贡献': 'a_sap_position_information_synchronization_ai_chinese_real',
    '经验及其他资质要求': 'a_sap_position_information_synchronization_ai_chinese_real',
    '部门职能类型名称': 'a_sap_position_information_synchronization_ai_chinese_real',
    '职务': 'a_sap_position_information_synchronization_ai_chinese_real',
    '职务类型': 'a_sap_position_information_synchronization_ai_chinese_real',
    '现职人数': 'a_sap_position_information_synchronization_ai_chinese_real',
    '开始日期': ['a_sap_reporting_relationship_ai_chinese_real',
                 'a_sap_employee_education_information_ai_chinese_real'],
    '结束日期': ['a_sap_reporting_relationship_ai_chinese_real',
                 'a_sap_employee_education_information_ai_chinese_real'],
    '人员号': 'a_sap_reporting_relationship_ai_chinese_real',
    '姓名': ['a_sap_reporting_relationship_ai_chinese_real', 'a_sap_personnel_basic_information_ai_chinese_real',
             'a_sap_employee_education_information_ai_chinese_real'],
    '入司日期': 'a_sap_reporting_relationship_ai_chinese_real',
    '工作性质': 'a_sap_reporting_relationship_ai_chinese_real',
    '是否管理机构': 'a_sap_reporting_relationship_ai_chinese_real',
    '兼职信息': 'a_sap_reporting_relationship_ai_chinese_real',
    '主管1姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '主管1职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '主管1职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '主管2姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '主管2职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '主管2职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理1姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理1职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理1职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理2姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理2职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理2职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理3姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理3职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理3职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理4姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理4职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '经理4职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监1姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监1职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监1职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监2姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监2职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监2职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监3姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监3职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监3职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监4姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监4职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '总监4职务': 'a_sap_reporting_relationship_ai_chinese_real',
    '一级机构负责人姓名': 'a_sap_reporting_relationship_ai_chinese_real',
    '一级机构负责人职位': 'a_sap_reporting_relationship_ai_chinese_real',
    '一级机构负责人职务': 'a_sap_reporting_relationship_ai_chinese_real',
}

table_info_schema_name_map = {
    '公司招聘编制使用情况表': 'a_sap_et_zthr_zp_list_ai_chinese_real',
    '员工教育详细信息表': 'a_sap_employee_education_information_ai_chinese_real',
    '员工基础信息表': 'a_sap_personnel_basic_information_ai_chinese_real',
    '公司部门机构介绍和岗位需求明细表': 'a_sap_position_information_synchronization_ai_chinese_real',
    '员工工作汇报关系表': 'a_sap_reporting_relationship_ai_chinese_real',
}

table_columns_map = {
    'a_sap_et_zthr_zp_list_ai_chinese_real': [
        '编制年度', '编制月度', '员工子组', '有效编制空缺', '创建日期', '年度可申请空缺数量', '季度可申请空缺数量',
        '月度可申请空缺数量', '年度编制数量', '季度编制数量', '月度编制数量', '特批编制数量', '拟在职人数',
        '有效但是没有报到空缺数', '写入日期', 'open数', '关闭数', '冻结数', '集团名称', '一级机构', '二级机构',
        '三级机构', '职级范围', ],
    'a_sap_employee_education_information_ai_chinese_real': [
        '人员工号', '姓名', '开始日期', '结束日期', '学历', '教育类型', '院校_培训机构', '国家', '证书', '第一专业', ],
    'a_sap_personnel_basic_information_ai_chinese_real': [
        '人员编号', '姓名', '雇佣状态', '职位', '入职日期', '部门负责人', '人事范围', '员工组', '员工子组文本',
        '上班地点', '英文名', '性别', '国籍', '民族', '籍贯', '身份证地址的省_直辖市', '开始参加工作日期',
        '员工本人联系号码', '一级机构名称', '二级机构名称', '三级机构名称', '职务名称', '员工工作性质文本',
        '直属上司工号', '直属上司姓名'
    ],
    'a_sap_position_information_synchronization_ai_chinese_real': [
        '集团', '一级机构', '二级机构', '三级机构', '职位', '成本类别名称', '岗位名称', '岗位属性名称', '角色定位',
        '岗位风险点', '岗位职责', '岗位任职资格', '绩效贡献', '经验及其他资质要求', '部门职能类型名称', '职务',
        '职务类型', '现职人数'],
    'a_sap_reporting_relationship_ai_chinese_real': [
        '开始日期', '结束日期', '人员号', '姓名', '入司日期', '工作性质', '一级机构', '二级机构', '三级机构', '职位',
        '职务名称', '是否管理机构', '兼职信息', '主管1姓名', '主管1职位', '主管1职务', '主管2姓名', '主管2职位',
        '主管2职务', '经理1姓名', '经理1职位', '经理1职务', '经理2姓名', '经理2职位', '经理2职务', '经理3姓名',
        '经理3职位', '经理3职务', '经理4姓名', '经理4职位', '经理4职务', '总监1姓名', '总监1职位', '总监1职务',
        '总监2姓名', '总监2职位', '总监2职务', '总监3姓名', '总监3职位', '总监3职务', '总监4姓名', '总监4职位',
        '总监4职务', '一级机构负责人姓名', '一级机构负责人职位', '一级机构负责人职务'],
}
a_sap_et_zthr_zp_list_ai_chinese_real = '''
-- 公司招聘编制使用情况表
create table public.a_sap_et_zthr_zp_list_ai_chinese_real(
编制年度 varchar(40) null,
编制月度 varchar(40) null,
员工子组 varchar(40) null,
有效编制空缺 integer null,
创建日期 varchar(40) null,
年度可申请空缺数量 varchar(40) null,
季度可申请空缺数量 varchar(40) null,
月度可申请空缺数量 varchar(40) null,
年度编制数量 varchar(40) null,
季度编制数量 varchar(40) null,
月度编制数量 varchar(40) null,
特批编制数量 varchar(40) null,
拟在职人数 varchar(40) null,
有效但是没有报到空缺数 varchar(40) null,
写入日期 varchar(40) null,
open数 varchar(40) null,
关闭数 varchar(40) null,
冻结数 varchar(40) null,
集团名称 varchar(40) null,
一级机构 varchar(40) null,
二级机构 varchar(40) null,
三级机构 varchar(40) null,
职级范围 varchar(40) null
 );'''

a_sap_employee_education_information_ai_chinese_real = '''
-- 员工教育信息表
create table public.a_sap_employee_education_information_ai_chinese_real (
人员工号 varchar(20) null,     
姓名  varchar(20) null, 
开始日期  varchar(40) null, 
结束日期  varchar(40) null,
学历  varchar(40) null,
教育类型  varchar(40) null,     
院校_培训机构  varchar(200) null,
国家  varchar(40) null,
证书  varchar(40) null,
第一专业  varchar(200) null,
FOREIGN KEY (人员工号) REFERENCES a_sap_personnel_basic_information_ai_chinese_real(人员编号),
FOREIGN KEY (人员工号) REFERENCES a_sap_reporting_relationship_ai_chinese_real(人员号)
);'''

a_sap_personnel_basic_information_ai_chinese_real = '''

-- 员工基础信息表
create table public.a_sap_personnel_basic_information_ai_chinese_real(
人员编号             varchar(30)       null,    
姓名                 varchar(50)   null,   
雇佣状态          varchar(30)     null, 
职位          varchar(100)     null,
入职日期              varchar(40)      null,
部门负责人          varchar(50)    null,    
人事范围          varchar(30)    null,
员工组          varchar(30)    null, 
员工子组文本          varchar(30)    null,
上班地点            varchar(30)    null,
英文名                varchar(50)    null,     
性别                varchar(30)    null,
国籍       varchar(30)       null,
民族       varchar(30)       null,
籍贯             varchar(100)       null,
身份证地址的省_直辖市             varchar(30)       null,     
开始参加工作日期             varchar(40)       null, 
员工本人联系号码             varchar(30)       null,    
一级机构名称         varchar(30)     null, 
二级机构名称         varchar(30)     null,
三级机构名称         varchar(30)     null,
职务名称            varchar(30)        null,
员工工作性质文本        varchar(30)        null,
直属上司工号        varchar(30)        null,         
直属上司姓名       varchar(30)        null,         
集团入职日期           varchar(40)        null
FOREIGN KEY (人员工号) REFERENCES a_sap_employee_education_information_ai_chinese_real(人员工号),
FOREIGN KEY (人员编号) REFERENCES a_sap_reporting_relationship_ai_chinese_real(人员号)
);
'''

a_sap_position_information_synchronization_ai_chinese_real = '''
-- 企业机构和岗位需求明细表
create table public.a_sap_position_information_synchronization_ai_chinese_real (
集团 varchar(40) null,
一级机构 varchar(40) null,
二级机构 varchar(40) null,
三级机构 varchar(40) null,
职位  varchar(60) null,
成本类别名称   varchar(40) null,
岗位名称    varchar(40) null,
岗位属性名称   varchar(70) null,
角色定位   text null,
岗位风险点   text null,
岗位职责   text null,
岗位任职资格   text null,
绩效贡献   text null,
经验及其他资质要求   text null,
部门职能类型名称   varchar(40) null,
职务  varchar(40) null,
职务类型    varchar(60) null,
现职人数  varchar(40) null

);'''

a_sap_reporting_relationship_ai_chinese_real = '''
-- 员工汇报关系表
create table public.a_sap_reporting_relationship_ai_chinese_real(
开始日期  varchar(40) null,
结束日期  varchar(40) null,           
人员号  varchar(40) null,   
姓名  varchar(60) null,
入司日期  varchar(40) null,
工作性质  varchar(40) null,
一级机构  varchar(40) null,
二级机构  varchar(40) null,
三级机构  varchar(40) null,
职位  varchar(100) null,
职务名称  varchar(40) null,
是否管理机构  varchar(40) null,
兼职信息  text null,
主管1姓名  varchar(40) null,
主管1职位  varchar(100) null,
主管1职务  varchar(40) null,
主管2姓名  varchar(40) null, 
主管2职位  varchar(1000) null,
主管2职务  varchar(40) null,
经理1姓名  varchar(40) null,
经理1职位  varchar(100) null,
经理1职务  varchar(40) null,
经理2姓名  varchar(40) null,
经理2职位  varchar(100) null,
经理2职务  varchar(40) null,
经理3姓名  varchar(40) null,
经理3职位  varchar(100) null,
经理3职务  varchar(40) null,
经理4姓名  varchar(40) null,
经理4职位  varchar(100) null,
经理4职务  varchar(40) null,
总监1姓名  varchar(40) null,
总监1职位  varchar(100) null,
总监1职务  varchar(40) null,
总监2姓名  varchar(40) null,
总监2职位  varchar(100) null,
总监2职务  varchar(40) null,
总监3姓名  varchar(40) null,
总监3职位  varchar(100) null,
总监3职务  varchar(40) null,
总监4姓名  varchar(40) null,
总监4职位  varchar(100) null,
总监4职务  varchar(40) null,
一级机构负责人姓名  varchar(40) null,
一级机构负责人职位  varchar(100) null,
一级机构负责人职务  varchar(40) null,
FOREIGN KEY (人员号) REFERENCES a_sap_employee_education_information_ai_chinese_real(人员工号),
FOREIGN KEY (人员号) REFERENCES a_sap_personnel_basic_information_ai_chinese_real(人员编号)
);'''