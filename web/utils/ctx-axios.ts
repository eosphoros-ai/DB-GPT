import axios from 'axios';

const api = axios.create({
  baseURL: process.env.API_BASE_URL ?? '',
});

api.defaults.timeout = 10000;

const ADMIN_API_PREFIX = '/api/v1/admin/';
const UNSAFE_METHODS = new Set(['post', 'put', 'patch', 'delete']);

const readBrowserCookie = (name: string) => {
  if (typeof document === 'undefined') return null;
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie
    .split(';')
    .map(item => item.trim())
    .find(item => item.startsWith(prefix));
  if (!cookie) return null;
  try {
    return decodeURIComponent(cookie.slice(prefix.length));
  } catch {
    return null;
  }
};

api.interceptors.request.use(request => {
  const method = request.method?.toLowerCase();
  if (!request.url?.startsWith(ADMIN_API_PREFIX)) return request;

  request.withCredentials = true;
  if (method && UNSAFE_METHODS.has(method)) {
    const csrfToken = readBrowserCookie('dbgpt_csrf');
    if (csrfToken) request.headers.set('X-CSRF-Token', csrfToken);
  }
  return request;
});

api.interceptors.response.use(
  response => response.data,
  err => Promise.reject(err),
);

export default api;
