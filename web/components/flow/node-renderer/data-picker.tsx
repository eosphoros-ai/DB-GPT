import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { DatePicker } from 'antd';
import dayjs from 'dayjs';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderDataPicker = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <DatePicker {...attr} defaultValue={dayjs(defaultValue)} onChange={onChange} />;
};
