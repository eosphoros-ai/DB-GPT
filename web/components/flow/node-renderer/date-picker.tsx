import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { DatePicker, DatePickerProps } from 'antd';
import dayjs from 'dayjs';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderDatePicker = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  const onChangeDate: DatePickerProps['onChange'] = (date, dateString) => {
    onChange(dateString);
  };

  return <DatePicker {...attr} className="w-full" defaultValue={dayjs(defaultValue)} onChange={onChangeDate} />;
};
