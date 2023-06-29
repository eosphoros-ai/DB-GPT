import { message } from 'antd';
import axios from 'axios';
import { isPlainObject } from 'lodash';

axios.defaults.baseURL = 'http://30.183.154.8:5000';

axios.defaults.timeout = 10000;

axios.interceptors.response.use(
  response => response.data,
	err => Promise.reject(err)
);

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
      .filter(k => qs[k] !== undefined && qs[k] !== '')
      .map(k => `${k}=${qs[k]}`)
      .join('&');
    if (str) {
      url += `?${str}`;
    }
  }
	return axios.get(url, {
    headers: DEFAULT_HEADERS
  }).then(res => res).catch(err => {
    message.error(err);
    Promise.reject(err);
  });
}

export const sendPostRequest = (url: string, body?: any) => {
  const reqBody = sanitizeBody(body);
  return axios.post(url, {
    body: reqBody,
    headers: DEFAULT_HEADERS
  }).then(res => res).catch(err => {
    message.error(err);
    Promise.reject(err);
  });
}