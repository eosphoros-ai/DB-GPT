import {
  CancelFeedbackAddParams,
  FeedbackAddParams,
  FeedbackReasonsResponse,
  RecommendQuestionParams,
  RecommendQuestionResponse,
  StopTopicParams,
} from '@/types/chat';
import { GET, POST, PUT } from '../index';

/**
 * 查询推荐问题
 */
export const getRecommendQuestions = (data?: RecommendQuestionParams) => {
  return GET<RecommendQuestionParams, RecommendQuestionResponse[]>(`/api/v1/question/list`, data);
};
/**
 * 拉踩原因类型
 */
export const getFeedbackReasons = () => {
  return GET<null, FeedbackReasonsResponse[]>(`/api/v1/conv/feedback/reasons`);
};
/**
 * 点赞/踩
 */
export const feedbackAdd = (data: FeedbackAddParams) => {
  return POST<FeedbackAddParams, Record<string, any>>(`/api/v1/conv/feedback/add`, data);
};
/**
 * 取消反馈
 */
export const cancelFeedback = (data: CancelFeedbackAddParams) => {
  return POST<CancelFeedbackAddParams, Record<string, any>>(`/api/v1/conv/feedback/cancel`, data);
};
/**
 * 终止话题
 */
export const stopTopic = (data: StopTopicParams) => {
  return POST<StopTopicParams, null>(
    `/api/v1/chat/topic/terminate?conv_id=${data.conv_id}&round_index=${data.round_index}`,
    data,
  );
};

/**
 * Harness engine availability (agent execution engines)
 */
export type HarnessEngineInfo = {
  engine: string;
  name: string;
  available: boolean;
  detail: string;
};

export type HarnessEnginesResponse = {
  engines: HarnessEngineInfo[];
  current: string;
};

export const getHarnessEngines = () => {
  return GET<null, HarnessEnginesResponse>(`/api/v1/chat/harness/engines`);
};

export const saveHarnessEngine = (engine: string) => {
  return PUT<{ engine: string }, { engine: string }>(`/api/v1/chat/harness/engine`, { engine });
};
