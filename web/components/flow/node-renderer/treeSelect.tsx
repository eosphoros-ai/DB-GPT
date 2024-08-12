import React, { useState } from 'react';
import { TreeSelect } from 'antd';
import type { TreeSelectProps } from 'antd';
import { IFlowNodeParameter } from "@/types/flow";
import { Label } from '@mui/icons-material';

type TextAreaProps = {
    data: IFlowNodeParameter;
    defaultValue: any;
    onChange: (value: any) => void;
  }
  const treeData = [
    {
      value: 'parent 1',
      title: 'parent 1',
      children: [
        {
          value: 'parent 1-0',
          title: 'parent 1-0',
          children: [
            {
              value: 'leaf1',
              title: 'leaf1',
            },
            {
              value: 'leaf2',
              title: 'leaf2',
            },
            {
              value: 'leaf3',
              title: 'leaf3',
            },      {
                value: 'leaf4',
                title: 'leaf4',
              },
              {
                value: 'leaf5',
                title: 'leaf5',
              },
              {
                value: 'leaf6',
                title: 'leaf6',
              },
            ],
          },
          {
            value: 'parent 1-1',
            title: 'parent 1-1',
            children: [
              {
                value: 'leaf11',
                title: <b style={{ color: '#08c' }}>leaf11</b>,
              },
            ],
        },
      ],
    },
  ];
  export const RenderTreeSelect = (params: TextAreaProps) => {
    // const { data, defaultValue, onChange } = params;
    // console.log(data.options);
    const [value, setValue] = useState<string>();

    const onChange = (newValue: string) => {
      setValue(newValue);
    };
    const focuss = ()=>{
        console.log('focus==========');
        
    }
    return (
        <TreeSelect
        fieldNames={{ label: 'label', value: 'value', children: 'children' }}  
        {...data.ui.attr} 
          style={{ width: '100%' }}
          value={defaultValue}
          treeDefaultExpandAll
          onChange={onChange}
          treeData={data.options}
        />

    //     <TreeSelect
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
}
