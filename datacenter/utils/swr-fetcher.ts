import axios, { AxiosRequestConfig } from 'axios';

export const postFetcher = <T>(uri: string, { arg }: { arg: T }) =>
  axios(uri, {
    method: 'POST',
    data: arg,
  }).then((r) => r.data);

export const createFetcher =
  (config: AxiosRequestConfig) =>
  <T>(url: string, { arg }: { arg: T }) =>
    axios({
      url,
      ...config,
      data: arg,
    }).then((r) => r.data);

export const fetcher = (...args: Parameters<typeof axios>) =>
  axios(...args).then((r) => r.data);
