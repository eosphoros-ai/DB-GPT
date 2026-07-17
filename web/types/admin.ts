export type AdminRole = 'system_admin' | 'operations_admin' | 'query_user';

export type AdminResourceType = 'DATASOURCE' | 'KNOWLEDGE_BASE' | 'AGENT';

export type AuditResult = 'success' | 'failed' | 'denied';

export interface AdminResult<T> {
  success: boolean;
  err_code: string | null;
  err_msg: string | null;
  data: T | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUser {
  user_id: string;
  login_name: string;
  display_name: string;
  role: AdminRole;
  is_active: boolean;
  gmt_created: string;
  disabled_at?: string | null;
}

export interface AdminLoginResponse {
  access_token: string;
  token_type: 'bearer';
  user: AdminUser;
}

export interface AdminUserListParams {
  page?: number;
  page_size?: number;
  login_name_like?: string;
  display_name_like?: string;
  role?: AdminRole;
  is_active?: boolean;
}

export interface AdminUserCreate {
  login_name: string;
  display_name: string;
  role: Exclude<AdminRole, 'system_admin'>;
  initial_password?: string;
  send_activation?: boolean;
  initial_account_set_ids?: string[];
}

export interface AdminUserUpdate {
  display_name?: string;
  role?: AdminRole;
  change_reason?: string;
  confirm_role_change?: boolean;
}

export interface AdminRoleInfo {
  role: AdminRole;
  permissions: string[];
  user_count: number;
}

export interface AccountSet {
  account_set_id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  gmt_created: string;
}

export interface AccountSetListParams {
  page?: number;
  page_size?: number;
  name_like?: string;
  is_active?: boolean;
}

export interface AccountSetInput {
  name: string;
  description?: string | null;
}

export interface AccountSetImpact {
  account_set_id: string;
  user_grant_count: number;
  resource_grant_count: number;
  resource_count: number;
  impact_token: string;
}

export interface ImpactConfirmation {
  reason: string;
  confirm_impact: true;
  impact_token: string;
}

export interface UserAccountGrant {
  grant_id: string;
  user_id: string;
  account_set_id: string;
  is_active: boolean;
  granted_by: string;
  revoked_by?: string | null;
  revoked_at?: string | null;
  revoke_reason?: string | null;
  gmt_created: string;
}

export interface UserResourceGrant {
  grant_id: string;
  user_id: string;
  resource_type: AdminResourceType;
  resource_id: string;
  account_set_id: string;
  is_active: boolean;
  granted_by: string;
  revoked_by?: string | null;
  revoked_at?: string | null;
  revoke_reason?: string | null;
  gmt_created: string;
}

export interface GrantListParams {
  page?: number;
  page_size?: number;
  is_active?: boolean;
}

export interface ResourceGrantListParams extends GrantListParams {
  resource_type?: AdminResourceType;
}

export interface RevokeImpact {
  grant_id: string;
  affected_resource_grants: number;
  affected_grants_detail: Array<Record<string, unknown>>;
  impact_token: string;
}

export interface AdminResource {
  resource_type: AdminResourceType;
  resource_id: string;
  name: string;
  account_set_id?: string | null;
}

export interface AdminResourceListParams {
  page?: number;
  page_size?: number;
  resource_type?: AdminResourceType;
  account_set_id?: string;
  unassigned?: boolean;
}

export interface ResourceImpact {
  resource_type: AdminResourceType;
  resource_id: string;
  current_account_set_id?: string | null;
  new_account_set_id: string;
  affected_resource_grants: number;
  affected_agent_grants: number;
  affected_grants_detail: Array<Record<string, unknown>>;
  impact_token: string;
}

export interface TokenUsageFilters {
  user_id?: string;
  account_set_id?: string;
  model?: string;
  date_from?: string;
  date_to?: string;
  role?: AdminRole;
}

export interface TokenUsageListParams extends TokenUsageFilters {
  page?: number;
  page_size?: number;
}

export interface TokenUsageSummary {
  stat_date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  call_count: number;
}

export interface TokenUsageDetail {
  call_id: string;
  request_id: string;
  session_id?: string | null;
  user_id: string;
  role_snapshot: AdminRole;
  account_set_id?: string | null;
  account_set_snapshot?: string | null;
  entry_resource_type?: AdminResourceType | null;
  entry_resource_id?: string | null;
  agent_id?: string | null;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  metering_source: 'provider' | 'estimated' | 'unknown';
  duration_ms?: number | null;
  status: 'success' | 'failed';
  error_type?: string | null;
  gmt_created: string;
}

export interface TokenDailyStat {
  stat_date: string;
  user_id: string;
  role_snapshot: AdminRole;
  account_set_id: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  call_count: number;
}

export interface AuditEvent {
  event_id: string;
  event_time: string;
  operator_user_id?: string | null;
  operator_role_snapshot?: AdminRole | null;
  target_account_set_id?: string | null;
  target_type: string;
  target_id?: string | null;
  action: string;
  result: AuditResult;
  source_ip?: string | null;
  user_agent?: string | null;
  request_id?: string | null;
  before_snapshot?: string | null;
  after_snapshot?: string | null;
  deny_reason?: string | null;
}

export interface AuditEventListParams {
  page?: number;
  page_size?: number;
  target_type?: string;
  action?: string;
  operator_user_id?: string;
  result?: AuditResult;
  date_from?: string;
  date_to?: string;
}
