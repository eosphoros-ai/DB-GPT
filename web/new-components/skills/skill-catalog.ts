export interface SkillPresentation {
  title: string;
  category: string;
  variant: string;
  accent: string;
  background: string;
  ink: string;
  subtitle: string;
  description: string;
  prompt: string;
  outcomes: string[];
  source?: string;
}
export const ADAPTED_SKILLS: Record<string, SkillPresentation> = {
  'antv-g2-chart': {
    title: 'G2 统计图表',
    category: '可视化',
    variant: 'charts',
    accent: '#665cf1',
    background: '#f1f3ff',
    ink: '#252946',
    subtitle: '把数据，画得更清楚',
    description: '根据字段与分析目的选择图表，处理坐标轴、图例和交互，让每张图都能回答一个问题。',
    prompt: '请根据我选择的数据，推荐适合的图表并说明理由，再做出可交互的可视化。',
    source: 'BMbJmx7wRmx19aDd4pKr',
    outcomes: ['图表选择与字段映射', '交互、标注与可读性', '空数据与异常值处理'],
  },
  'datapulse-viz-design': {
    title: '增长脉搏',
    category: '设计',
    variant: 'growth',
    accent: '#6461e8',
    background: '#f3f5fb',
    ink: '#242c46',
    subtitle: 'SaaS 与产品增长',
    description: '用清晰的指标、趋势和转化漏斗，组织获客、激活与留存分析，适合产品和增长团队。',
    prompt: '请用「增长脉搏」风格，基于我选择的数据做一份清晰的增长分析看板，优先展示核心趋势与转化。',
    source: 'MlAxGEmgzP0qz5o3DYpe',
    outcomes: ['增长指标与转化趋势', '轻量蓝紫色视觉', '分群与留存口径'],
  },
  'nexusai-viz-design': {
    title: '智能体工作台',
    category: '设计',
    variant: 'workspace',
    accent: '#6058de',
    background: '#f1f3f5',
    ink: '#293046',
    subtitle: 'AI 服务与自动化运营',
    description: '让任务队列、服务状态和运行指标各就其位，帮助团队快速找到需要处理的事项。',
    prompt: '请用「智能体工作台」风格组织我选择的数据，展示运行状态、关键指标和待处理事项。',
    source: 'nBqQeyK2RAJ4X3AjNkJL',
    outcomes: ['任务与状态分层', '运行效率与异常定位', '列表和详情协同'],
  },
  'learnhub-viz-design': {
    title: '学习成长',
    category: '设计',
    variant: 'learning',
    accent: '#429079',
    background: '#fff8e9',
    ink: '#39312e',
    subtitle: '课程、进度与学员表现',
    description: '用温暖的卡片与清楚的进度表达，呈现课程参与、完成情况和需要关注的学习群体。',
    prompt: '请用「学习成长」风格，基于所选数据展示学习进度、课程完成情况与需要关注的群体。',
    source: 'MKjpgNDy9gLdREJZxnl4',
    outcomes: ['课程进度与完成率', '友好而清楚的层次', '班级与学习群体比较'],
  },
  'brutal-viz-design': {
    title: '海报式营销',
    category: '设计',
    variant: 'poster',
    accent: '#e04a39',
    background: '#f6f2e9',
    ink: '#232324',
    subtitle: '活动复盘与品牌表达',
    description: '用醒目的标题、明确的块面和硬边结构，突出营销活动的关键结果与贡献。',
    prompt: '请用「海报式营销」风格，把我选择的数据做成一份有重点、易读的营销活动复盘。',
    source: '2k8mGw6PzbZLzBDj5ond',
    outcomes: ['关键结果优先', '强轮廓与对比色', '渠道与活动复盘'],
  },
  'pawspa-viz-design': {
    title: '宠物门店运营',
    category: '设计',
    variant: 'pet',
    accent: '#e87b36',
    background: '#fff6e9',
    ink: '#4b352a',
    subtitle: '预约、服务与回访',
    description: '以奶油底和橙色重点呈现预约、服务组合与复购情况，兼顾门店效率和亲和感。',
    prompt: '请用「宠物门店运营」风格，基于所选数据展示预约、服务收入、员工排班与客户回访。',
    source: 'xABv5yMK9Ypwz1N3ZjQo',
    outcomes: ['预约与服务结构', '会员回访与复购', '员工工作量分布'],
  },
  'serenityspa-viz-design': {
    title: '美业预约管理',
    category: '设计',
    variant: 'spa',
    accent: '#795e71',
    background: '#f8f2ee',
    ink: '#533d50',
    subtitle: '预约、房间与会员经营',
    description: '用梅色导航、轻盈的周历与鼠尾草色状态，串起预约、房间安排和会员经营。',
    prompt: '请用「美业预约管理」风格，基于所选数据展示预约到店、房间负载、会员复购及服务收入。',
    source: 'yYZjko7mRo8aXgBOdn6x',
    outcomes: ['预约与到店情况', '房间和服务时段负载', '会员分层与复购'],
  },
};
const existing: Record<string, Partial<SkillPresentation>> = {
  'agent-browser': {
    title: '浏览器助手',
    category: '自动化',
    variant: 'workspace',
    subtitle: '浏览、查找与操作',
    description: '让 AI 通过浏览器访问页面、查找信息并完成明确的网页操作。',
    outcomes: ['网页内容读取', '多步操作', '结果核验'],
  },
  'csv-data-analysis': {
    title: '表格数据分析',
    category: '数据',
    variant: 'charts',
    subtitle: '从文件找到线索',
    description: '分析 CSV 与 Excel 数据，检查质量、发现趋势，并整理为清楚的图表与结论。',
    outcomes: ['表格理解', '趋势与分布', '分析报告'],
  },
  'dashboard-builder': {
    title: '可编辑看板搭建',
    category: '可视化',
    variant: 'growth',
    subtitle: '从数据到可用看板',
    description: '基于所选数据源规划指标、生成查询，并创建可筛选、可编辑的数据看板。',
    outcomes: ['指标规划', '查询校验', '原生可编辑看板'],
  },
  'financial-report-analyzer': {
    title: '财报分析',
    category: '数据',
    variant: 'spa',
    subtitle: '理解财务表现',
    description: '提取财报核心指标，比较经营表现，并整理有依据的财务分析报告。',
    outcomes: ['财务指标', '同期比较', '报告整理'],
  },
  'skill-creator': {
    title: '技能创作助手',
    category: '自动化',
    variant: 'workspace',
    subtitle: '保存你的工作方法',
    description: '把重复使用的方法整理成技能，明确适用场景、执行步骤与验证方式。',
    outcomes: ['场景定义', '工作流程', '技能文件'],
  },
  'walmart-sales-analyzer': {
    title: '零售销售分析',
    category: '数据',
    variant: 'growth',
    subtitle: '门店、趋势与影响因素',
    description: '结合 Walmart 销售数据比较门店、观察时间趋势并生成分析报告。',
    outcomes: ['门店比较', '趋势分析', '可视化报告'],
  },
};
export function getSkillPresentation(skill: {
  name: string;
  description?: string;
  skill_type?: string;
}): SkillPresentation {
  if (ADAPTED_SKILLS[skill.name]) return ADAPTED_SKILLS[skill.name];
  const known = existing[skill.name] || {};
  return {
    title: skill.name,
    category: skill.skill_type === 'data_analysis' ? '数据' : '自动化',
    variant: 'charts',
    accent: '#6570ad',
    background: '#f1f3fa',
    ink: '#2a3144',
    subtitle: '我的工作方法',
    description: skill.description || '打开技能，查看使用方法。',
    prompt: `请使用「${known.title || skill.name}」，帮我完成以下任务：`,
    outcomes: ['查看技能说明', '结合当前任务使用'],
    ...known,
  };
}
export const SKILL_CATEGORIES = ['全部', '设计', '数据', '可视化', '自动化'];
