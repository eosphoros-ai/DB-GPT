import React from 'react';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Slider } from 'antd';

export const renderSlider = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <Slider className="mt-8 nodrag" {...attr} tooltip={{ open: true }} />;
};
