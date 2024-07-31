import { message } from 'antd';
import axios from './ctx-axios';
import { isPlainObject } from 'lodash';

const DEFAULT_HEADERS = {
  'content-type': 'application/json',
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

export const sendGetRequest = (url: string, qs?: { [key: string]: any }) => {
  if (qs) {
    const str = Object.keys(qs)
      .filter((k) => qs[k] !== undefined && qs[k] !== '')
      .map((k) => `${k}=${qs[k]}`)
      .join('&');
    if (str) {
      url += `?${str}`;
    }
  }
  return axios
    .get<null, any>('/api' + url, {
      headers: DEFAULT_HEADERS,
    })
    .then((res) => res)
    .catch((err) => {
      message.error(err);
      Promise.reject(err);
    });
};

export const sendSpaceGetRequest = (url: string, qs?: { [key: string]: any }) => {
  if (qs) {
    const str = Object.keys(qs)
      .filter((k) => qs[k] !== undefined && qs[k] !== '')
      .map((k) => `${k}=${qs[k]}`)
      .join('&');
    if (str) {
      url += `?${str}`;
    }
  }
  return axios
    .get<null, any>(url, {
      headers: DEFAULT_HEADERS,
    })
    .then((res) => res)
    .catch((err) => {
      message.error(err);
      Promise.reject(err);
    });
};

export const sendPostRequest = (url: string, body?: any) => {
  const reqBody = sanitizeBody(body);
  return axios
    .post<null, any>('/api' + url, {
      body: reqBody,
      headers: DEFAULT_HEADERS,
    })
    .then((res) => res)
    .catch((err) => {
      message.error(err);
      Promise.reject(err);
    });
};

export const sendSpacePostRequest = (url: string, body?: any) => {
  return axios
    .post<null, any>(url, body, {
      headers: DEFAULT_HEADERS,
    })
    .then((res) => res)
    .catch((err) => {
      message.error(err);
      Promise.reject(err);
    });
};

export const sendSpaceUploadPostRequest = (url: string, body?: any) => {
  return axios
    .post<null, any>(url, body)
    .then((res) => res)
    .catch((err) => {
      message.error(err);
      Promise.reject(err);
    });
};
