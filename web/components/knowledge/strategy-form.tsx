import { IChunkStrategyResponse } from '@/types/knowledge';
import { Alert, Button, Form, FormListFieldData, Input, InputNumber, Radio, RadioChangeEvent } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
const { TextArea } = Input;

type IProps = {
  strategies: Array<IChunkStrategyResponse>;
  docType: string;
  field: FormListFieldData;
  fileName: string;
};

/**
 * render strategies by doc type and file suffix
 */
export default function StrategyForm({ strategies, docType, fileName, field }: IProps) {
  let filleSuffix = '';
  if (docType === 'DOCUMENT') {
    // filter strategy by file suffix
    const arr = fileName.split('.');
    filleSuffix = arr[arr.length - 1];
  }
  const ableStrategies = filleSuffix ? strategies.filter((i) => i.suffix.indexOf(filleSuffix) > -1) : strategies;
  const [selectedStrategy, setSelectedStrategy] = useState<string>();
  const { t } = useTranslation();
  const DEFAULT_STRATEGY = {
    name: t('Automatic'),
    desc: t('Automatic_desc'),
  };

  function radioChange(e: RadioChangeEvent) {
    setSelectedStrategy(e.target.value);
  }

  function syncDocument() {}

  function renderStrategyParamForm() {
    if (!selectedStrategy) {
      return null;
    }
    if (selectedStrategy === DEFAULT_STRATEGY.name) {
      return <p className="my-4">{DEFAULT_STRATEGY.desc}</p>;
    }
    const parameters = ableStrategies?.filter((i) => i.name === selectedStrategy)[0].parameters;
    if (!parameters || !parameters.length) {
      return <Alert className="my-2" type="warning" message={t('No_parameter')} />;
    }
    return (
      <div className="mt-2">
        {parameters?.map((param) => (
          <Form.Item
            key={`param_${param.param_name}`}
            label={`${param.param_name}: ${param.param_type}`}
            name={[field!.name, 'chunk_parameters', param.param_name]}
            rules={[{ required: true, message: t('Please_input_the_name') }]}
          >
            {param.param_type === 'int' ? <InputNumber className="w-full" min={1} /> : <TextArea className="w-full" rows={4} maxLength={6} />}
          </Form.Item>
        ))}
      </div>
    );
  }
  return (
    <>
      <Form.Item name={[field!.name, 'chunk_parameters', 'chunk_strategy']} initialValue={DEFAULT_STRATEGY.name}>
        <Radio.Group style={{ marginTop: 16 }} onChange={radioChange}>
          <Radio value={DEFAULT_STRATEGY.name}>{DEFAULT_STRATEGY.name}</Radio>
          {ableStrategies.map((strategy) => (
            <Radio key={`strategy_radio_${strategy.name}`} value={strategy.name}>
              {strategy.name}
            </Radio>
          ))}
        </Radio.Group>
      </Form.Item>
      {renderStrategyParamForm()}
      <Form.Item className="mt-2" wrapperCol={{ offset: 8, span: 16 }}>
        <Button type="primary" onClick={syncDocument}>
          {t('Sync')}
        </Button>
      </Form.Item>
    </>
  );
}
