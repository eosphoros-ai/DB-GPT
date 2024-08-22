import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { DatePicker } from 'antd';

export const renderDatePicker = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <DatePicker {...attr} className="w-full" placeholder="please select a date" />;
};
