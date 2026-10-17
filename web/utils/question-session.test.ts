import { describe, expect, it } from 'vitest';
import { checkQuestionResponse, QuestionSession, questionSlots } from './question-session';
import { ReActSSEState } from './react-sse-parser';

const ask = (request_id: string, sequence?: number) => ({
  type: 'question.asked' as const,
  request_id,
  conv_id: 'conversation',
  sequence,
  questions: [`Question ${request_id}`],
});

describe('request-bound event ordering', () => {
  it.each(['question.replied', 'question.rejected'] as const)('does not clear B on late %s for A', type => {
    const session = new QuestionSession();
    session.apply(ask('A', 1));
    session.apply(ask('B', 2));
    session.apply({ type, request_id: 'A' });
    session.apply(ask('A', 1));
    expect(session.current?.request_id).toBe('B');
    session.apply({ type, request_id: 'B' });
    session.apply(ask('B', 2));
    expect(session.current).toBeNull();
  });

  it('ignores a first-seen older ask using the server sequence', () => {
    const session = new QuestionSession();
    session.apply(ask('B', 2));
    session.apply(ask('A', 1));
    expect(session.current?.request_id).toBe('B');
  });

  it('does not resurrect an ask delivered after its own terminal event', () => {
    const session = new QuestionSession();
    session.apply({ type: 'question.replied', request_id: 'A' });
    session.apply(ask('A'));
    expect(session.current).toBeNull();
  });

  it('ignores duplicate/changed payloads for an immutable request_id', () => {
    const session = new QuestionSession();
    session.apply(ask('A'));
    session.apply({ ...ask('A'), questions: ['Different question'] });
    expect(session.current?.questions).toEqual(['Question A']);
  });

  it('ignores malformed identity and a different conversation', () => {
    const session = new QuestionSession();
    session.apply(ask('A'));
    session.apply({ type: 'question.replied' });
    session.apply({ type: 'question.replied', request_id: 'A', conv_id: 'elsewhere' });
    session.apply({ ...ask('B'), conv_id: 'elsewhere' }, 'conversation');
    expect(session.current?.request_id).toBe('A');
  });

  it('keeps the same protection in the real ReAct SSE parser', () => {
    const parser = new ReActSSEState();
    parser.processEvent(ask('A', 1));
    parser.processEvent(ask('B', 2));
    parser.processEvent({ type: 'question.rejected', request_id: 'A' });
    parser.processEvent(ask('A', 1));
    expect(parser.getPendingQuestion()?.request_id).toBe('B');
  });
});

it('keeps null slots at the beginning, middle and end; strings become free text', () => {
  const slots = questionSlots([null, 'Second', {}, { question: 'Fourth' }, 2]);
  expect(slots.map(q => q?.question ?? null)).toEqual([null, 'Second', null, 'Fourth', null]);
  expect(slots[1]).toMatchObject({ options: [], header: '', custom: true, multiple: false });
});

it.each([
  { success: false, data: { success: false, request_id: 'A' } },
  { success: true, data: { success: true, request_id: 'B' } },
])('does not equate HTTP 200 with the matching business success: %j', async body => {
  await expect(checkQuestionResponse(new Response(JSON.stringify(body)), 'A')).rejects.toThrow();
});
