import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Input } from 'antd';

const { Password } = Input;

export const renderPassword = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <Password {...attr} placeholder='input password' />;
};
