import i18n from '@/app/i18n';
import { getUserId } from '@/utils';
import { message } from 'antd';
import { isPlainObject } from 'lodash';
import axios from './ctx-axios';

const DEFAULT_HEADERS = {
  'content-type': 'application/json',
  'User-Id': getUserId(),
};

// body 字段 trim
const sanitizeBody = (obj: Record<string, any>): string => {
  // simple shallow copy to avoid changing original obj
  if (!isPlainObject(obj)) return JSON.stringify(obj);
  const resObj = { ...obj };
  for (const key in resObj) {
    const val = resObj[key];
    if (typeof val === 'string') {
      resObj[key] = val.trim();
    }
  }
  return JSON.stringify(resObj);
};

// 从 axios 错误中提取友好提示文案(走 i18n)。
// 网络层失败(err.response 不存在)按 err.code 细分:超时 / 其他网络错误。
// 浏览器对 CORS 拦截 / 连接拒绝 / 断网 都只给 ERR_NETWORK,JS 无法进一步区分,
// 只能给方向性提示。传给 message.error 的必须是 string/ReactNode,不能是原始
// axios 对象(antd 渲染对象会抛异常 → 触发 Next.js 错误页)。
const formatErrTip = (err: any): string => {
  if (!err) return i18n.t('request.error.default', { status: '?' });
  // 网络层失败:浏览器拦截或服务不可达,无 response
  if (!err.response) {
    if (err.code === 'ECONNABORTED') {
      return i18n.t('request.error.timeout');
    }
    return i18n.t('request.error.network');
  }
  // HTTP 错误:优先用服务端返回的 err_msg / message
  const data = err.response.data;
  if (data) {
    if (typeof data === 'string') return data;
    if (typeof data.err_msg === 'string') return data.err_msg;
    if (typeof data.message === 'string') return data.message;
  }
  return i18n.t('request.error.default', { status: err.response.status || '?' });
};

export const sendGetRequest = (url: string, qs?: { [key: string]: any }) => {
  if (qs) {
    const str = Object.keys(qs)
      .filter(k => qs[k] !== undefined && qs[k] !== '')
      .map(k => `${k}=${qs[k]}`)
      .join('&');
    if (str) {
      url += `?${str}`;
    }
  }
  return axios
    .get<null, any>('/api' + url, {
      headers: DEFAULT_HEADERS,
    })
    .then(res => res)
    .catch(err => {
      message.error(formatErrTip(err));
      return Promise.reject(err);
    });
};

export const sendSpaceGetRequest = (url: string, qs?: { [key: string]: any }) => {
  if (qs) {
    const str = Object.keys(qs)
      .filter(k => qs[k] !== undefined && qs[k] !== '')
      .map(k => `${k}=${qs[k]}`)
      .join('&');
    if (str) {
      url += `?${str}`;
    }
  }
  return axios
    .get<null, any>(url, {
      headers: DEFAULT_HEADERS,
    })
    .then(res => res)
    .catch(err => {
      message.error(formatErrTip(err));
      return Promise.reject(err);
    });
};

export const sendPostRequest = (url: string, body?: any) => {
  const reqBody = sanitizeBody(body);
  return axios
    .post<null, any>('/api' + url, {
      body: reqBody,
      headers: DEFAULT_HEADERS,
    })
    .then(res => res)
    .catch(err => {
      message.error(formatErrTip(err));
      return Promise.reject(err);
    });
};

export const sendSpacePostRequest = (url: string, body?: any) => {
  return axios
    .post<null, any>(url, body, {
      headers: DEFAULT_HEADERS,
    })
    .then(res => res)
    .catch(err => {
      message.error(formatErrTip(err));
      return Promise.reject(err);
    });
};

export const sendSpaceUploadPostRequest = (url: string, body?: any) => {
  return axios
    .post<null, any>(url, body)
    .then(res => res)
    .catch(err => {
      message.error(formatErrTip(err));
      return Promise.reject(err);
    });
};
