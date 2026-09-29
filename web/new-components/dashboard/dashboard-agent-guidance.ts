export const buildPublicationBindingAgentPrompt = (
  widgetTitle: string,
  filterLabels: string[],
) => {
  const filters = filterLabels.length ? filterLabels.join('、') : '当前看板的全局筛选器';
  return [
    `请为“${widgetTitle}”补全分享页筛选数据绑定。`,
    `需要支持的筛选器：${filters}。`,
    '请保持组件现有指标定义、图表类型和编辑查询不变，只补充 Schema 1.3 publication。',
    '发布查询必须是只读参数化 SQL，并只冻结该组件筛选、分组和聚合所需的最小数据集。',
    '请同时配置 filter_fields、group_by、measures、output_columns、row_mode、sort 和 max_output_rows，并校验筛选前后结果。',
    '先给出可验证的修改方案，不要直接应用。',
  ].join('\n');
};
