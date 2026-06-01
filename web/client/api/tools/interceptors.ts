import i18n from '@/app/i18n';
import { notification } from 'antd';
import { AxiosError } from 'axios';
import { ApiResponse, FailedTuple, ResponseType, SuccessTuple } from '../';

export type ApiInterceptorOptions = {
  /** Skip error notifications (e.g. background list refresh). */
  silent?: boolean;
};

const isNetworkFailure = (err: unknown): boolean =>
  err instanceof AxiosError && !err.response;

/** Axios wrapper or bare API JSON from a misconfigured client. */
const normalizeResponseBody = <T>(response: unknown): ResponseType<T> | null => {
  if (!response || typeof response !== 'object') {
    return null;
  }
  const maybe = response as Record<string, unknown>;
  if ('success' in maybe && 'data' in maybe && !('status' in maybe)) {
    return maybe as ResponseType<T>;
  }
  if (maybe.data && typeof maybe.data === 'object') {
    const inner = maybe.data as Record<string, unknown>;
    if ('success' in inner && 'data' in inner) {
      return inner as ResponseType<T>;
    }
  }
  return null;
};

const notifyRequestError = (description: string, options?: ApiInterceptorOptions) => {
  if (options?.silent) return;
  notification.error({
    message: i18n.t('request_error'),
    description,
  });
};

/**
 * Response processing
 *
 * @param promise request
 * @param ignoreCodes ignore error codes
 * @param options silent: do not show error toasts
 * @returns
 */
export const apiInterceptors = <T = any, D = any>(
  promise: Promise<ApiResponse<T, D>> | Promise<ResponseType<T>>,
  ignoreCodes?: '*' | (number | string)[],
  options?: ApiInterceptorOptions,
) => {
  if (!promise || typeof (promise as Promise<unknown>).then !== 'function') {
    const err = new Error('Invalid API request');
    console.warn('[API]', err.message);
    return Promise.resolve([err, null, null, null] as FailedTuple<T, D>);
  }

  return Promise.resolve(promise)
    .then<SuccessTuple<T, D>>(response => {
      const data = normalizeResponseBody<T>(response);
      if (!data) {
        throw new Error('Network Error!');
      }
      if (!data.success) {
        if (ignoreCodes === '*' || (data.err_code && ignoreCodes && ignoreCodes.includes(data.err_code))) {
          return [null, data.data, data, response as ApiResponse<T, D>];
        }
        notifyRequestError(data?.err_msg ?? i18n.t('api_interface_abnormal'), options);
      }
      return [null, data.data, data, response as ApiResponse<T, D>];
    })
    .catch<FailedTuple<T, D>>((err: Error | AxiosError<T, D>) => {
      let errMessage = err.message;
      if (err instanceof AxiosError) {
        try {
          const { err_msg } = JSON.parse(err.request.response) as ResponseType<null>;
          err_msg && (errMessage = err_msg);
        } catch {
          /* empty */
        }
      }
      if (isNetworkFailure(err)) {
        console.warn('[API] network error:', errMessage);
      } else {
        notifyRequestError(errMessage || i18n.t('network_error'), options);
      }
      return [err, null, null, null];
    });
};
