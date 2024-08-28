import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { DatePicker } from 'antd';
import type { DatePickerProps } from 'antd';

type Props = {
  formValuesChange:any,
  data: IFlowNodeParameter;
  onChange?: (value: any) => void;
};
export const renderDatePicker = (params: Props) => {
  const { data ,formValuesChange} = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  const onChange: DatePickerProps['onChange'] = (date, dateString) => {
    console.log(date, dateString);
    formValuesChange({
      [data.name]:dateString
    })
  };


  return <DatePicker  onChange={onChange} {...attr} className="w-full" placeholder="please select a date" />;
};
