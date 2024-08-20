import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Col, InputNumber, Row, Slider, Space } from 'antd';
import type { InputNumberProps } from 'antd';
import React, { useState } from 'react';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderSlider = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});
  const [inputValue, setInputValue] = useState(defaultValue);
  const onChangeSlider: InputNumberProps['onChange'] = (newValue) => {
    setInputValue(newValue);
    onChange(newValue);
  };

  return (
    <>
      {data?.ui?.show_input ? (
        <Row>
          <Col span={12}>
            <Slider className="w-full nodrag" {...attr} onChange={onChangeSlider} value={inputValue} />
          </Col>
          <Col span={4}>
            <InputNumber {...attr} style={{ margin: '0 16px' }} value={inputValue} onChange={onChangeSlider} />
          </Col>
        </Row>
      ) : (
        <Slider className="w-full nodrag"  {...attr} onChange={onChangeSlider} value={inputValue} />
      )}
    </>
  );
};
