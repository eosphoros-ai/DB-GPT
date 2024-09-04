import axios from 'axios';

const api = axios.create({
  baseURL: 'http://127.0.0.1:5670'
});

api.defaults.timeout = 10000;

api.interceptors.response.use(
  response => response.data,
	err => Promise.reject(err)
);

export default api;