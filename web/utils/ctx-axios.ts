import axios from 'axios';

const api = axios.create({
  baseURL: process.env.API_BASE_URL,
});

api.defaults.timeout = 10000;

api.interceptors.response.use(
  response => response.data,
	err => Promise.reject(err)
);

export default api;