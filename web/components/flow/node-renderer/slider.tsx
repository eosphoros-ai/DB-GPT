import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Slider } from 'antd';

export const renderSlider = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <>
      {data.is_list ? <Slider range className='mt-8 nodrag' {...attr} /> : <Slider className='mt-8 nodrag' {...attr} />}
    </>
  );
};
