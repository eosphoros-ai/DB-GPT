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
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className="p-2 text-sm">
      <TextArea {...attr} defaultValue={defaultValue} onChange={(e) => onChange(e.target.value)} {...data.ui.attr.autosize} rows={4} />
    </div>
  );
};
