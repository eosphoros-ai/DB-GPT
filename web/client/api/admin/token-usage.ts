import {
  AdminResult,
  Page,
  TokenDailyStat,
  TokenUsageDetail,
  TokenUsageFilters,
  TokenUsageListParams,
  TokenUsageSummary,
} from '@/types/admin';
import api from '@/utils/ctx-axios';

const TOKEN_USAGE_BASE = '/api/v1/admin/token-usage';

export const getTokenUsageSummary = (statDate?: string) =>
  api.get<unknown, AdminResult<TokenUsageSummary>>(`${TOKEN_USAGE_BASE}/summary`, {
    params: statDate ? { stat_date: statDate } : undefined,
  });

export const getTokenUsageDetail = (params: TokenUsageListParams = {}) =>
  api.get<unknown, AdminResult<Page<TokenUsageDetail>>>(`${TOKEN_USAGE_BASE}/detail`, { params });

export const getTokenUsageDaily = (params: TokenUsageFilters = {}) =>
  api.get<unknown, AdminResult<TokenDailyStat[]>>(`${TOKEN_USAGE_BASE}/daily`, { params });
