import { IFlowNodeParameter } from '@/types/flow';
import { Input } from 'antd';
import { uiAtrrtUnderlineToHump } from '@/utils/flow';

const { TextArea } = Input;

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderTextArea = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  uiAtrrtUnderlineToHump(data?.ui?.attr?.autosize || {});

  return <TextArea {...data.ui.attr} defaultValue={defaultValue} onChange={(e) => onChange(e.target.value)} {...data.ui.autosize} rows={4} />;
};
