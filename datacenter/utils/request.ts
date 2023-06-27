import axios from 'axios';

axios.defaults.baseURL = 'http://30.183.153.244:5000';

axios.defaults.timeout = 10000;

axios.interceptors.response.use(
  response => response.data,
	err => Promise.reject(err)
);

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
	axios.get(url, {
    headers: {
      "Content-Type": 'text/plain'
    }
	}).then(res => {
		console.log(res, 'res');
	}).catch(err => {
		console.log(err, 'err');
	})
}
