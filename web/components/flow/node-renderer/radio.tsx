import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Radio } from 'antd';

export const renderRadio = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className='bg-white p-2 rounded'>
      <Radio.Group {...attr} options={data.options} />
    </div>
  );
};
