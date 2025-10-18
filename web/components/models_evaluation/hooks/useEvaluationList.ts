import { apiInterceptors } from '@/client/api';
import { getBenchmarkTaskList } from '@/client/api/models_evaluation';
import { EvaluationData, getBenchmarkTaskListRequest } from '@/types/models_evaluation';
import { useRequest } from 'ahooks';
import { message } from 'antd';

interface UseEvaluationListProps {
  filterValue?: string;
  type?: string;
}

export const useEvaluationList = (props: UseEvaluationListProps) => {
  const { filterValue = '', type = 'all' } = props;

  const {
    data,
    loading,
    run: getModelsEvaluation,
    refresh,
  } = useRequest(
    async (page = 1, page_size = 20) => {
      const params: getBenchmarkTaskListRequest = {
        page,
        page_size,
        filter_param: filterValue || undefined,
        sys_code: type === 'all' ? undefined : type,
      };

      const [_, data] = await apiInterceptors(getBenchmarkTaskList(params));

      return data as EvaluationData;
    },
    {
      manual: true,
      onError: e => {
        message.error(e.message || '获取评估列表失败');
      },
    },
  );

  return {
    data,
    loading,
    getModelsEvaluation,
    refresh,
  };
};
