import { DashboardLayoutTemplateId } from './dashboard-layout-templates';
import { LAYOUT_TEMPLATES_ENABLED } from './dashboard-release-features';

export interface DashboardTemplate {
  id: string;
  title: string;
  question: string;
  audience: string;
  layoutId: DashboardLayoutTemplateId;
  prompt: string;
}

export const DASHBOARD_TEMPLATES: DashboardTemplate[] = [
  {
    id: 'executive-health',
    title: '经营健康总览',
    question: '经营是否健康，哪里最需要管理层介入？',
    audience: '管理层',
    layoutId: 'metric-overview',
    prompt:
      '请基于当前选中的数据库规划一张“经营健康总览”看板。面向管理层，目标是判断整体经营是否健康、哪些信号需要立即介入。按总览 KPI、趋势变化、结构贡献、异常明细四层组织；优先使用 T-29 到 T 的滚动日期筛选。异常判断必须规划为程序规则，阈值列为待确认项，不要让模型凭文字下结论。请先给出完整分析规划、每个组件的业务问题和布局理由，等待我确认后再生成，未确认前不要创建看板或生成 SQL。',
  },
  {
    id: 'growth-diagnosis',
    title: '增长异常诊断',
    question: '增长变化由什么驱动，异常从何时、何处分化？',
    audience: '业务分析',
    layoutId: 'trend-focus',
    prompt:
      '请基于当前选中的数据库规划一张“增长异常诊断”看板。面向业务分析人员，目标是解释增长变化的驱动因素并定位异常。按核心增长指标、时间趋势、分群贡献、异常对象明细四层组织；同时给出同比或环比口径，并使用可滚动的相对日期。异常检测只能使用上一周期、滚动平均或业务目标值等确定性基线，把方向、窗口、样本要求和阈值列为用户待确认项；AI 只解释计算证据。请先给出完整分析规划、指标口径和布局理由，等待我确认后再生成，未确认前不要创建看板或生成 SQL。',
  },
  {
    id: 'regional-intervention',
    title: '区域干预优先级',
    question: '哪个区域或门店需要先处理，依据是什么？',
    audience: '区域运营',
    layoutId: 'operations-detail',
    prompt:
      '请基于当前选中的数据库规划一张“区域干预优先级”看板。面向区域运营负责人，目标是识别最需要优先处理的区域或门店。按全局状态、区域对比、趋势与结构、可执行明细四层组织，突出由程序规则计算的异常幅度、影响规模和可下钻对象；日期使用 T-6 到 T 的滚动范围，异常阈值列为待确认项。请先给出完整分析规划、排序逻辑和布局理由，等待我确认后再生成，未确认前不要创建看板或生成 SQL。',
  },
];

if (LAYOUT_TEMPLATES_ENABLED) {
  for (const template of DASHBOARD_TEMPLATES) {
    template.prompt += ` 请在规划中设置 layout_template 为 "${template.layoutId}"，使用这套布局组织已有指标和图表。`;
  }
}

export const DASHBOARD_TEMPLATE_BY_ID = Object.fromEntries(
  DASHBOARD_TEMPLATES.map(template => [template.id, template]),
) as Record<string, DashboardTemplate>;
