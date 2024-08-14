import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Radio } from 'antd';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderRadio = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className="bg-white p-2 rounded">
      <Radio.Group
        {...attr}
        options={data.options}
        onChange={(e) => {
          onChange(e.target.value);
        }}
        defaultValue={defaultValue}
      />
    </div>
  );
};
