import { getUserId } from '@/utils/storage';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.API_BASE_URL ?? '',
});

api.defaults.timeout = 10000;

api.interceptors.request.use(request => {
  const userId = getUserId();
  if (userId) {
    request.headers.set(HEADER_USER_ID_KEY, userId);
  }
  return request;
});

api.interceptors.response.use(
  response => response.data,
  err => Promise.reject(err),
);

export default api;
