import { AdminResourceType, AdminResult, AdminRole } from '@/types/admin';
import { AxiosError } from 'axios';
import { ReactNode } from 'react';

export const ROLE_LABELS: Record<AdminRole, string> = {
  system_admin: '系统管理员',
  operations_admin: '运营管理员',
  query_user: '查询用户',
};

export const ROLE_COLORS: Record<AdminRole, string> = {
  system_admin: 'red',
  operations_admin: 'blue',
  query_user: 'green',
};

export const RESOURCE_LABELS: Record<AdminResourceType, string> = {
  DATASOURCE: '数据源',
  KNOWLEDGE_BASE: '知识库',
  AGENT: '智能体',
};

export function requireAdminData<T>(result: AdminResult<T>): T {
  if (!result.success || result.data === null) {
    throw new Error(result.err_msg || '请求失败');
  }
  return result.data;
}

export function getAdminErrorMessage(error: unknown, fallback = '操作失败，请重试') {
  if (error instanceof Error && !(error instanceof AxiosError)) return error.message || fallback;
  const axiosError = error as AxiosError<{ detail?: string | { message?: string }; err_msg?: string }>;
  const detail = axiosError.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail.message === 'string') return detail.message;
  return axiosError.response?.data?.err_msg || fallback;
}

export function formatAdminDate(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
}

export function AdminPageHeader({
  title,
  description,
  extra,
}: {
  title: string;
  description?: string;
  extra?: ReactNode;
}) {
  return (
    <div className='mb-5 flex flex-wrap items-start justify-between gap-3'>
      <div className='min-w-0'>
        <h1 className='m-0 text-2xl font-semibold leading-8 text-gray-900'>{title}</h1>
        {description && <p className='mb-0 mt-1 text-sm text-gray-500'>{description}</p>}
      </div>
      {extra}
    </div>
  );
}
