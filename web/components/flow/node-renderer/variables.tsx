import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Input } from 'antd';

export const renderVariables = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <Input {...attr} className='w-full' placeholder='please input' allowClear />;
};
