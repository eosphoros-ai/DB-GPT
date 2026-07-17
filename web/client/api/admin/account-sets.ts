import {
  AccountSet,
  AccountSetImpact,
  AccountSetInput,
  AccountSetListParams,
  AdminResult,
  ImpactConfirmation,
  Page,
} from '@/types/admin';
import api from '@/utils/ctx-axios';

const ACCOUNT_SETS_BASE = '/api/v1/admin/account-sets';

export const listAccountSets = (params: AccountSetListParams = {}) =>
  api.get<unknown, AdminResult<Page<AccountSet>>>(ACCOUNT_SETS_BASE, { params });

export const getAccountSet = (accountSetId: string) =>
  api.get<unknown, AdminResult<AccountSet>>(`${ACCOUNT_SETS_BASE}/${encodeURIComponent(accountSetId)}`);

export const createAccountSet = (body: AccountSetInput) =>
  api.post<unknown, AdminResult<AccountSet>>(ACCOUNT_SETS_BASE, body);

export const updateAccountSet = (accountSetId: string, body: Partial<AccountSetInput>) =>
  api.patch<unknown, AdminResult<AccountSet>>(`${ACCOUNT_SETS_BASE}/${encodeURIComponent(accountSetId)}`, body);

export const getAccountSetImpact = (accountSetId: string) =>
  api.get<unknown, AdminResult<AccountSetImpact>>(`${ACCOUNT_SETS_BASE}/${encodeURIComponent(accountSetId)}/impact`);

export const toggleAccountSetActive = (accountSetId: string, activate: boolean, confirmation?: ImpactConfirmation) =>
  api.post<unknown, AdminResult<AccountSet>>(
    `${ACCOUNT_SETS_BASE}/${encodeURIComponent(accountSetId)}/${activate ? 'activate' : 'deactivate'}`,
    activate ? {} : confirmation,
  );
