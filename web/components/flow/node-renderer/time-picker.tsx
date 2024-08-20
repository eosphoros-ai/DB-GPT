import React from 'react';
import type { TimePickerProps } from 'antd';
import { TimePicker } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderTimePicker = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  const onChangeTime: TimePickerProps['onChange'] = (time, timeString) => {
    onChange(timeString);
  };

  return <TimePicker {...attr} className="w-full" defaultValue={defaultValue} onChange={onChangeTime} placeholder="please select a moment" />;
};
