import React from 'react';
import { TimePicker } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';

export const renderTimePicker = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <TimePicker {...attr} className="w-full" placeholder="please select a moment" />;
};
