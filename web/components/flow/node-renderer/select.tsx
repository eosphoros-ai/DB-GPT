import { IFlowNodeParameter } from '@/types/flow';
import { Select } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderSelect = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <Select {...attr} className="w-full nodrag" placeholder="please select" defaultValue={defaultValue} options={data.options} onChange={onChange} />
  );
};
