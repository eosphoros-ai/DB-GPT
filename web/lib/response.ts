import { ERROR_CODE } from '@/utils/constants';
import type { NextApiRequest, NextApiResponse } from 'next';

type IApiResponse<T = any> = {
  statusCode?: number;
  success: boolean;
  message: string;
  data: T;
  errorCode?: ERROR_CODE | (string & {});
};

type Methods = 'GET' | 'OPTIONS' | 'PUT' | 'POST' | 'PATCH' | 'DELETE' | (string & {});

export function response<T = any>(res: NextApiResponse, options?: Partial<IApiResponse<T>>) {
  const { statusCode = 200, message, data = null, errorCode } = options ?? {};

  res.status(statusCode).json({
    success: statusCode === 200 && !errorCode,
    err_msg: message ?? (statusCode === 200 && !errorCode ? 'successful' : 'failed'),
    data,
    err_code: errorCode ?? (statusCode === 200 ? undefined : statusCode),
  });
}

export function checkAllowMethods(res: NextApiResponse, method: string = '', methods: Methods[]) {
  if (!method || !methods.includes(method)) {
    response(res, { statusCode: 405 });
    return false;
  }
  return true;
}

export function checkAuthorized(req: NextApiRequest, res: NextApiResponse) {
  if (!req.session) {
    response(res, { statusCode: 401 });
    return false;
  }
  return true;
}
