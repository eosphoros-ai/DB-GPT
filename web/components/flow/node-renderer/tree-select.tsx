import React, { useState } from 'react';
import { TreeSelect } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};
export const RenderTreeSelect = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className="p-2 text-sm">
      <TreeSelect
      className="w-full nodrag" 
        fieldNames={{ label: 'label', value: 'value', children: 'children' }}
        {...attr}
        style={{ width: '100%' }}
        value={defaultValue}
        treeDefaultExpandAll
        onChange={onChange}
        treeData={data.options}
      />
    </div>
  );
};
