import { IFlowNodeParameter } from '@/types/flow';
import { Input } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';

const { TextArea } = Input;

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderTextArea = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  convertKeysToCamelCase(data?.ui?.attr?.autosize || {});

  return (
    <div className="p-2 text-sm">
      <TextArea {...data.ui.attr} defaultValue={defaultValue} onChange={(e) => onChange(e.target.value)} {...data.ui.attr.autosize} rows={4} />
    </div>
  );
};
