import React, { useState } from 'react';
import type { TimePickerProps } from 'antd';
import { TimePicker } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};
export const RenderTimePicker = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  const onChangeTime: TimePickerProps['onChange'] = (time, timeString) => {
    onChange(timeString);
  };

  return (
    <div className="p-2 text-sm">
      <TimePicker {...attr} className="w-full" defaultValue={defaultValue} onChange={onChangeTime} />
    </div>
  );
};
