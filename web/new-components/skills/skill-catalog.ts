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
