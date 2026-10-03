import { describe, expect, it } from 'vitest';
import { DASHBOARD_TEMPLATES } from './dashboard-templates';

describe('dashboard business templates', () => {
  it('offers the three decision templates and always pauses for confirmation', () => {
    expect(DASHBOARD_TEMPLATES.map(item => item.title)).toEqual([
      '经营健康总览',
      '增长异常诊断',
      '区域干预优先级',
    ]);
    DASHBOARD_TEMPLATES.forEach(template => {
      expect(template.prompt).toContain('等待我确认');
      expect(template.prompt).toContain('未确认前不要创建看板或生成 SQL');
      expect(template.prompt).toContain('布局理由');
    });
  });
});
