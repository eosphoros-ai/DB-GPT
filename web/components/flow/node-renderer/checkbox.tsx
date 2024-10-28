import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Checkbox } from 'antd';

export const renderCheckbox = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    data.options?.length > 0 && (
      <div className='bg-white p-2 rounded'>
        <Checkbox.Group {...attr} options={data.options} />
      </div>
    )
  );
};
