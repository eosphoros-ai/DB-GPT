import { IFlowNodeParameter } from '@/types/flow';
import { Input } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';
import classNames from 'classnames';

const { TextArea } = Input;

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderTextArea = (params: Props) => {
  const { data, defaultValue, onChange } = params;

  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className={classNames({ 'mb-3': attr.showCount === true })}>
      <TextArea className='nowheel' {...attr} defaultValue={defaultValue} onChange={onChange} />
    </div>
  );
};
