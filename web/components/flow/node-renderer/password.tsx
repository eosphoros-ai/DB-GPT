import { IFlowNodeParameter } from '@/types/flow';
import { Input } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';

const { Password } = Input;

export const renderPassword = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <Password {...attr} placeholder="input password" />;
};
