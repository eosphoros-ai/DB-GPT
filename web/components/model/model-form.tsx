import { apiInterceptors, getSupportModels, startModel } from '@/client/api';
import { SupportModel, SupportModelParams } from '@/types/model';
import { Button, Form, Select, Tooltip, message } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { renderModelIcon } from '@/components/chat/header/model-selector';
import ModelParams from './model-params';
const { Option } = Select;

function ModelForm({ onCancel, onSuccess }: { onCancel: () => void; onSuccess: () => void }) {
  const { t } = useTranslation();
  const [models, setModels] = useState<Array<SupportModel> | null>([]);
  const [selectedModel, setSelectedModel] = useState<SupportModel>();
  const [params, setParams] = useState<Array<SupportModelParams> | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [form] = Form.useForm();

  async function getModels() {
    const [, res] = await apiInterceptors(getSupportModels());
    if (res && res.length) {
      setModels(
        res.sort((a: SupportModel, b: SupportModel) => {
          if (a.enabled && !b.enabled) {
            return -1;
          } else if (!a.enabled && b.enabled) {
            return 1;
          } else {
            return a.model.localeCompare(b.model);
          }
        }),
      );
    }
    setModels(res);
  }

  useEffect(() => {
    getModels();
  }, []);

  function handleChange(value: string, option: any) {
    setSelectedModel(option.model);
    setParams(option.model.params);
  }

  async function onFinish(values: any) {
    if (!selectedModel) {
      return;
    }
    delete values.model;
    setLoading(true);
    const [, , data] = await apiInterceptors(
      startModel({
        host: selectedModel.host,
        port: selectedModel.port,
        model: selectedModel.model,
        worker_type: selectedModel?.worker_type,
        params: values,
      }),
    );
    setLoading(false);
    if (data?.success === true) {
      onSuccess && onSuccess();
      return message.success(t('start_model_success'));
    }
  }

  return (
    <Form labelCol={{ span: 8 }} wrapperCol={{ span: 16 }} onFinish={onFinish} form={form}>
      <Form.Item label="Model" name="model" rules={[{ required: true, message: t('model_select_tips') }]}>
        <Select showSearch onChange={handleChange}>
          {models?.map((model) => (
            <Option key={model.model} value={model.model} label={model.model} model={model} disabled={!model.enabled}>
              {renderModelIcon(model.model)}
              <Tooltip title={model.enabled ? model.model : t('download_model_tip')}>
                <span className="ml-2">{model.model}</span>
              </Tooltip>
              <Tooltip title={model.enabled ? `${model.host}:${model.port}` : t('download_model_tip')}>
                <p className="inline-block absolute right-4">
                  <span>{model.host}:</span>
                  <span>{model.port}</span>
                </p>
              </Tooltip>
            </Option>
          ))}
        </Select>
      </Form.Item>
      <ModelParams params={params} form={form} />
      <div className="flex justify-center">
        <Button type="primary" htmlType="submit" loading={loading}>
          {t('submit')}
        </Button>
        <Button className="ml-10" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </Form>
  );
}

export default ModelForm;
