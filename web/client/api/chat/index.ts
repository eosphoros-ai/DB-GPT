import {
  CancelFeedbackAddParams,
  FeedbackAddParams,
  FeedbackReasonsResponse,
  RecommendQuestionParams,
  RecommendQuestionResponse,
  StopTopicParams,
} from '@/types/chat';
import { GET, POST } from '../index';

/**
 * Query recommended questions
 */
export const getRecommendQuestions = (data?: RecommendQuestionParams) => {
  return GET<RecommendQuestionParams, RecommendQuestionResponse[]>(`/api/v1/question/list`, data);
};
/**
 * Dislike reason types
 */
export const getFeedbackReasons = () => {
  return GET<null, FeedbackReasonsResponse[]>(`/api/v1/conv/feedback/reasons`);
};
/**
 * Like / dislike feedback
 */
export const feedbackAdd = (data: FeedbackAddParams) => {
  return POST<FeedbackAddParams, Record<string, any>>(`/api/v1/conv/feedback/add`, data);
};
/**
 * Cancel feedback
 */
export const cancelFeedback = (data: CancelFeedbackAddParams) => {
  return POST<CancelFeedbackAddParams, Record<string, any>>(`/api/v1/conv/feedback/cancel`, data);
};
/**
 * Terminate topic
 */
export const stopTopic = (data: StopTopicParams) => {
  return POST<StopTopicParams, null>(
    `/api/v1/chat/topic/terminate?conv_id=${data.conv_id}&round_index=${data.round_index}`,
    data,
  );
};
