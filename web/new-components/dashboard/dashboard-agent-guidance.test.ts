import { describe, expect, it } from 'vitest';
import { buildPublicationBindingAgentPrompt } from './dashboard-agent-guidance';

describe('dashboard agent guidance', () => {
  it('asks for a minimal, read-only publication binding without changing the chart', () => {
    const prompt = buildPublicationBindingAgentPrompt('门店销售排行', ['日期范围', '门店多选']);

    expect(prompt).toContain('门店销售排行');
    expect(prompt).toContain('日期范围、门店多选');
    expect(prompt).toContain('只读参数化 SQL');
    expect(prompt).toContain('最小数据集');
    expect(prompt).toContain('保持组件现有指标定义、图表类型和编辑查询不变');
    expect(prompt).toContain('不要直接应用');
  });
});
