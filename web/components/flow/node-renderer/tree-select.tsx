import React, { useState } from 'react';
import { TreeSelect } from 'antd';
import type { TreeSelectProps } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { Label } from '@mui/icons-material';
import { convertKeysToCamelCase } from '@/utils/flow';

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};
export const RenderTreeSelect = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  const [dropdownVisible, setDropdownVisible] = useState(false);

  const handleDropdownVisibleChange = (visible: boolean | ((prevState: boolean) => boolean)) => {
    setDropdownVisible(visible);
  };
  console.log(data);
  

  return (
    <div className="p-2 text-sm">
      <TreeSelect
        fieldNames={{ label: 'label', value: 'value', children: 'children' }}
        {...attr}
        style={{ width: '100%' }}
        value={defaultValue}
        treeDefaultExpandAll
        onChange={onChange}
        treeData={data.options}
        onDropdownVisibleChange={handleDropdownVisibleChange}
      />
    </div>

    // TODO: Implement the TreeSelect component
    //   <TreeSelect
    //   showSearch
    //   style={{ width: '100%' }}
    //   value={value}
    //   dropdownStyle={{ maxHeight: 400, overflow: 'auto' }}
    //   placeholder="Please select"
    //   allowClear
    //   treeDefaultExpandAll
    //   onChange={onChange}
    //   treeData={treeData}
    //   getPopupContainer={() => document.body}
    // />
  );
};
