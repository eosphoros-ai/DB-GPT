import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Select } from 'antd';

export const renderSelect = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data?.ui?.attr || {});

  return <Select {...attr} className='w-full nodrag' placeholder='please select' options={data.options} />;
};
