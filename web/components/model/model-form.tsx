import { apiInterceptors, getSupportModels, startModel } from '@/client/api';
import { renderModelIcon } from '@/components/chat/header/model-selector';
import { StartModelParams, SupportModel, SupportModelParams } from '@/types/model';
import { AutoComplete, Button, Form, Select, Tooltip, message } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import ModelParams from './model-params';

const { Option } = Select;
const FormItem = Form.Item;

function ModelForm({ onCancel, onSuccess }: { onCancel: () => void; onSuccess: () => void }) {
  const { t } = useTranslation();
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [models, setModels] = useState<Array<SupportModel> | null>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>();
  const [params, setParams] = useState<Array<SupportModelParams> | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [form] = Form.useForm();

  const [groupedModels, setGroupedModels] = useState<{ [key: string]: SupportModel[] }>({});
  const [providers, setProviders] = useState<string[]>([]);

  async function getModels() {
    const [, res] = await apiInterceptors(getSupportModels());
    if (res && res.length) {
      const sortedModels = res.sort((a: SupportModel, b: SupportModel) => {
        if (a.enabled && !b.enabled) return -1;
        if (!a.enabled && b.enabled) return 1;
        return a.model.localeCompare(b.model);
      });

      setModels(sortedModels);

      const grouped = sortedModels.reduce((acc: { [key: string]: SupportModel[] }, model) => {
        const provider = model.provider;
        if (!acc[provider]) acc[provider] = [];
        acc[provider].push(model);
        return acc;
      }, {});

      setGroupedModels(grouped);
      setProviders(Object.keys(grouped).sort());
    }
  }

  useEffect(() => {
    getModels();
  }, []);

  function handleProviderChange(value: string) {
    setSelectedProvider(value);
    form.resetFields();
    form.setFieldValue('provider', value);

    // Get the parameters of the first model of the current provider as the default parameters
    const providerModels = groupedModels[value] || [];
    if (providerModels.length > 0) {
      const firstModel = providerModels[0];
      if (firstModel?.params) {
        setParams(Array.isArray(firstModel.params) ? firstModel.params : [firstModel.params]);
      }
    }
  }

  async function onFinish(values: any) {
    if (!selectedProvider) return;

    setLoading(true);
    try {
      // Get the selected model information (if any)
      const selectedModel = groupedModels[selectedProvider]?.find(m => m.model === values.name);
      const params: StartModelParams = {
        host: selectedModel?.host || '',
        port: selectedModel?.port || 0,
        model: values.name,
        worker_type: selectedModel?.worker_type || 'llm',
        params: values,
      };
      const [, , data] = await apiInterceptors(startModel(params));
      if (data?.success) {
        message.success(t('start_model_success'));
        onSuccess?.();
      }
    } catch (_error) {
      message.error(t('start_model_failed'));
    } finally {
      setLoading(false);
    }
  }

  const renderTooltipContent = (model: SupportModel) => (
    <div className='max-w-md'>
      <div className='whitespace-pre-wrap markdown-body'>
        <ReactMarkdown>{model.description || model.model}</ReactMarkdown>
      </div>
      <div className='mt-2 text-xs opacity-75'>
        {model.enabled ? `${model.host}:${model.port}` : t('download_model_tip')}
      </div>
    </div>
  );

  return (
    <Form form={form} labelCol={{ span: 8 }} wrapperCol={{ span: 16 }} onFinish={onFinish}>
      <FormItem label='Provider' name='provider' rules={[{ required: true, message: t('provider_select_tips') }]}>
        <Select onChange={handleProviderChange} placeholder={t('model_select_provider')}>
          {providers.map(provider => (
            <Option key={provider} value={provider}>
              {provider}
            </Option>
          ))}
        </Select>
      </FormItem>

      {selectedProvider && params && (
        <>
          <FormItem
            label={t('model_deploy_name')}
            name='name'
            rules={[{ required: true, message: t('model_please_input_name') }]}
          >
            <AutoComplete
              style={{ width: '100%' }}
              placeholder={t('model_select_or_input_model')}
              options={groupedModels[selectedProvider]?.map(model => ({
                value: model.model,
                label: (
                  <div className='flex items-center w-full'>
                    <div className='flex items-center'>
                      {renderModelIcon(model.model)}
                      <Tooltip title={renderTooltipContent(model)} placement='right'>
                        <span className='ml-2'>{model.model}</span>
                      </Tooltip>
                    </div>
                  </div>
                ),
              }))}
              filterOption={(inputValue, option) =>
                option!.value.toUpperCase().indexOf(inputValue.toUpperCase()) !== -1
              }
            />
          </FormItem>

          <ModelParams params={params.filter(p => p.param_name !== 'name')} form={form} />
        </>
      )}

      <div className='flex justify-center space-x-4'>
        <Button type='primary' htmlType='submit' loading={loading}>
          {t('submit')}
        </Button>
        <Button onClick={onCancel}>{t('cancel')}</Button>
      </div>
    </Form>
  );
}

export default ModelForm;
