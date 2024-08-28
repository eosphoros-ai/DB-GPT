import { IFlowNodeParameter } from '@/types/flow';
import { Select } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';

export const renderSelect = (data: IFlowNodeParameter) => {  
  const attr = convertKeysToCamelCase(data?.ui?.attr || {});

  return <Select {...attr} className="w-full nodrag" placeholder="please select" options={data.options} />;
};
