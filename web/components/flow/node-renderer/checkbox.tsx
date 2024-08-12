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
      <Checkbox.Group
        {...attr}
        options={data.options}
        disabled
        defaultValue={defaultValue}
        onChange={onChange}
      />
    )
  );
};
