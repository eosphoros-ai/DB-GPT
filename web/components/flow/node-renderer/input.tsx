import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Input } from 'antd';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderInput = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className="p-2 text-sm">
      <Input
        {...attr}
        className="w-full"
        placeholder="please input"
        defaultValue={defaultValue}
        onChange={(e) => {
          onChange(e.target.value);
        }}
      />
    </div>
  );
};
