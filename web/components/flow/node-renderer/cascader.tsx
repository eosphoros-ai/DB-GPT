import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Cascader } from 'antd';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderCascader = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <Cascader 
      {...attr}
      options={data.options} 
      defaultValue={defaultValue}
      placeholder="Please select" 
      className="w-full nodrag"
      onChange={onChange} 
    />
  );
};
