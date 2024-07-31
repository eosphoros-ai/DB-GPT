import { AxiosError } from 'axios';
import { ApiResponse, FailedTuple, SuccessTuple } from '../';
import { notification } from 'antd';

/**
 * Response processing
 *
 * @param promise request
 * @param ignoreCodes ignore error codes
 * @returns
 */
export const apiInterceptors = <T = any, D = any>(promise: Promise<ApiResponse<T, D>>, ignoreCodes?: '*' | (number | string)[]) => {
  return promise
    .then<SuccessTuple<T, D>>((response) => {
      const { data } = response;
      if (!data) {
        throw new Error('Network Error!');
      }
      if (!data.success) {
        if (ignoreCodes === '*' || (data.err_code && ignoreCodes && ignoreCodes.includes(data.err_code))) {
          return [null, data.data, data, response];
        } else {
          notification.error({
            message: `Request error`,
            description: data?.err_msg ?? 'The interface is abnormal. Please try again later',
          });
        }
      }
      return [null, data.data, data, response];
    })
    .catch<FailedTuple>((err: Error | AxiosError) => {
      notification.error({
        message: `Request error`,
        description: err.message,
      });
      return [err, null, null, null];
    });
};
