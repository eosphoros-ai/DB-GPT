import { cleanAgentAnswer } from '@/utils/clean-agent-answer';
import { describe, expect, it } from 'vitest';

describe('legacy completed answers', () => {
  it('shows the usable answer from terminate without protocol text', () => {
    const answer = '总行数：**6,435 行**。\n\n`SELECT COUNT(*) FROM walmart_sales`';
    expect(
      cleanAgentAnswer(
        `Thought: Need to return the result.\nPhase: 完成\nAction: terminate\nAction Input: ${JSON.stringify({ output: answer })}`,
      ),
    ).toBe(answer);
  });
  it('does not mistake ordinary prose or a partial envelope for a complete answer', () => {
    const answer = '## 分析结果\n\n金额总和为 42。';
    expect(cleanAgentAnswer(answer)).toBe(answer);
    expect(cleanAgentAnswer('Action: terminate\nAction Input: {"output":')).toContain('terminate');
  });
});
