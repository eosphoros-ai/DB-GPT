import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { checkQuestionResponse, isQuestionEvent, PendingQuestion, QuestionSession } from '@/utils/question-session';
import { useCallback, useRef, useState } from 'react';

export function useQuestionSession(apiBaseUrl = process.env.API_BASE_URL ?? '') {
  const session = useRef(new QuestionSession());
  const submitting = useRef(new Set<string>());
  const [pendingQuestion, setPendingQuestion] = useState<PendingQuestion | null>(null);

  const handleQuestionEvent = useCallback((event: unknown, conversationId?: string) => {
    if (!isQuestionEvent(event)) return false;
    setPendingQuestion(session.current.apply(event, conversationId));
    return true;
  }, []);

  const clearQuestions = useCallback(() => {
    const current = session.current.current;
    if (current) session.current.resolve(current.request_id);
    setPendingQuestion(null);
  }, []);

  const submit = useCallback(
    async (requestId: string, answers?: string[][]) => {
      const current = session.current.current;
      if (!current || current.request_id !== requestId) throw new Error('这条问题已更新，请回答当前显示的问题。');
      if (answers && answers.length !== current.questions.length) throw new Error('问题与答案数量不一致，请重新作答。');
      if (submitting.current.has(requestId)) return;
      submitting.current.add(requestId);
      try {
        const response = await fetch(
          `${apiBaseUrl}/api/v1/chat/question/${encodeURIComponent(requestId)}/${answers ? 'reply' : 'reject'}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', [HEADER_USER_ID_KEY]: getUserId() ?? '' },
            ...(answers ? { body: JSON.stringify({ answers }) } : {}),
          },
        );
        await checkQuestionResponse(response, requestId);
        setPendingQuestion(session.current.resolve(requestId));
      } finally {
        submitting.current.delete(requestId);
      }
    },
    [apiBaseUrl],
  );

  const replyQuestion = useCallback((requestId: string, answers: string[][]) => submit(requestId, answers), [submit]);
  const rejectQuestion = useCallback((requestId: string) => submit(requestId), [submit]);
  return { pendingQuestion, handleQuestionEvent, clearQuestions, replyQuestion, rejectQuestion };
}
