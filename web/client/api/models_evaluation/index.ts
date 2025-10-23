import type { createBenchmarkTaskRequest, getBenchmarkTaskListRequest } from '@/types/models_evaluation';
import { getUserId } from '@/utils';
import { GET, POST } from '../index';

const userId = getUserId();

//get benchmark task list
export const getBenchmarkTaskList = (data: getBenchmarkTaskListRequest) => {
  return GET<getBenchmarkTaskListRequest, Record<string, any>>(`/api/v1/evaluate/benchmark_task_list`, data, {
    headers: {
      'user-id': userId,
    },
  });
};

// create benchmark task
export const createBenchmarkTask = (data: createBenchmarkTaskRequest) => {
  return POST<createBenchmarkTaskRequest, Record<string, any>>(`/api/v1/evaluate/execute_benchmark_task`, data, {
    headers: {
      'user-id': userId,
    },
  });
};
