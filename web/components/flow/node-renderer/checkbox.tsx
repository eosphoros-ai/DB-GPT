import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Checkbox } from 'antd';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderCheckbox = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    data.options?.length > 0 && (
      <div className="bg-white p-2 rounded">
        <Checkbox.Group {...attr} options={data.options} defaultValue={defaultValue} onChange={onChange} />
      </div>
    )
  );
};
