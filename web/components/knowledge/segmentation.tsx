import { apiInterceptors, getChunkStrategies, syncBatchDocument } from '@/client/api';
import { File, IChunkStrategyResponse, ISyncBatchParameter, StepChangeParams } from '@/types/knowledge';
import { Alert, Button, Collapse, Form, Spin, message } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import StrategyForm from './strategy-form';

type IProps = {
  spaceName: string;
  docType: string;
  handleStepChange: (params: StepChangeParams) => void;
  files?: Array<File>;
};

type FieldType = {
  fileStrategies: Array<ISyncBatchParameter>;
};

export default function Segmentation(props: IProps) {
  const { spaceName, docType, files, handleStepChange } = props;
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState<boolean>();
  const [strategies, setStrategies] = useState<Array<IChunkStrategyResponse>>([]);

  async function getStrategies() {
    setLoading(true);
    const [, allStrategies] = await apiInterceptors(getChunkStrategies());
    setLoading(false);
    setStrategies((allStrategies || [])?.filter((i) => i.type.indexOf(docType) > -1));
  }

  useEffect(() => {
    getStrategies();
  }, []);

  const handleFinish = async (data: FieldType) => {
    if (checkParameter(data)) {
      setLoading(true);
      const [, result] = await apiInterceptors(syncBatchDocument(spaceName, data.fileStrategies));
      setLoading(false);
      if (result?.tasks?.length > 0) {
        handleStepChange({
          label: 'finish',
        });
        return message.success(`Segemation task start successfully. task id: ${result?.tasks.join(',')}`);
      }
    }
  };

  function checkParameter(data: FieldType) {
    const { fileStrategies } = data;
    let checked = true;
    fileStrategies.map((item) => {
      if (!item?.chunk_parameters?.chunk_strategy) {
        message.error(`Please select chunk strategy for ${item.name}.`);
        checked = false;
      }
    });
    return checked;
  }

  function renderStrategy() {
    if (!strategies || !strategies.length) {
      return <Alert message={`Cannot find one strategy for ${docType} type knowledge.`} type="warning" />;
    }
    return (
      <Form.List name="fileStrategies">
        {(fields) => {
          switch (docType) {
            case 'TEXT':
            case 'URL':
              return fields?.map((field) => (
                // field [{name: 0, key: 0, isListField: true, fieldKey: 0}, {name: 1, key: 1, isListField: true, fieldKey: 1}]
                <StrategyForm strategies={strategies} docType={docType} fileName={files![field.name].name} field={field} />
              ));
            case 'DOCUMENT':
              return (
                <Collapse defaultActiveKey={0}>
                  {fields?.map((field) => (
                    // field [{name: 0, key: 0, isListField: true, fieldKey: 0}, {name: 1, key: 1, isListField: true, fieldKey: 1}]
                    <Collapse.Panel header={`${field.name}. ${files![field.name].name}`} key={field.key}>
                      <StrategyForm strategies={strategies} docType={docType} fileName={files![field.name].name} field={field} />
                    </Collapse.Panel>
                  ))}
                </Collapse>
              );
          }
        }}
      </Form.List>
    );
  }

  return (
    <Spin spinning={loading}>
      <Form
        labelCol={{ span: 6 }}
        wrapperCol={{ span: 18 }}
        labelAlign="right"
        form={form}
        size="large"
        className="mt-4"
        layout="horizontal"
        name="basic"
        autoComplete="off"
        initialValues={{
          fileStrategies: files,
        }}
        onFinish={handleFinish}
      >
        {renderStrategy()}
        <Form.Item className="mt-4">
          <Button
            onClick={() => {
              handleStepChange({ label: 'back' });
            }}
            className="mr-4"
          >{`${t('Back')}`}</Button>
          <Button type="primary" htmlType="submit" loading={loading}>
            {t('Process')}
          </Button>
        </Form.Item>
      </Form>
    </Spin>
  );
}
