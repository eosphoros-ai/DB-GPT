import React, { useState } from 'react';
import type { TimePickerProps } from 'antd';
import { TimePicker } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};
export const RenderTimePicker = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  const [value, setValue] = useState(defaultValue);

  // dayjs.extend(customParseFormat);

  const onChangeTime: TimePickerProps['onChange'] = (time, timeString) => {
    onChange(timeString);
    setValue(time);
  };

  return <TimePicker style={{ width: '100%' }} {...data.ui.attr} value={value} onChange={onChangeTime} />;
};
