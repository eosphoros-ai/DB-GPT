import { apiInterceptors, createModel, getSupportModels } from '@/client/api';
import { renderModelIcon } from '@/components/chat/header/model-selector';
import { ConfigurableParams } from '@/types/common';
import { StartModelParams, SupportModel } from '@/types/model';
import { AutoComplete, Button, Form, Select, Tooltip, message } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import ConfigurableForm from '../common/configurable-form';

const { Option } = Select;
const FormItem = Form.Item;

// The supported worker types
const WORKER_TYPES = ['llm', 'text2vec', 'reranker'];

function ModelForm({ onCancel, onSuccess }: { onCancel: () => void; onSuccess: () => void }) {
  const { t } = useTranslation();
  const [_, setModels] = useState<Array<SupportModel> | null>([]);
  const [selectedWorkerType, setSelectedWorkerType] = useState<string>();
  const [selectedProvider, setSelectedProvider] = useState<string>();
  const [params, setParams] = useState<Array<ConfigurableParams> | null>(null);
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
      // Note: Initially do not set providers, wait for worker_type selection before setting
      setProviders([]);
    }
  }

  useEffect(() => {
    getModels();
  }, []);

  // Filter and set available providers based on worker_type
  function updateProvidersByWorkerType(workerType: string) {
    const availableProviders = new Set<string>();
    Object.entries(groupedModels).forEach(([provider, models]) => {
      if (models.some(model => model.worker_type === workerType)) {
        availableProviders.add(provider);
      }
    });
    setProviders(Array.from(availableProviders).sort());
  }

  function handleWorkerTypeChange(value: string) {
    setSelectedWorkerType(value);
    setSelectedProvider(undefined);
    form.resetFields();
    form.setFieldValue('worker_type', value);
    updateProvidersByWorkerType(value);
  }

  function handleProviderChange(value: string) {
    setSelectedProvider(value);
    form.setFieldValue('provider', value);

    // Get the params of the first model that matches the selected worker_type under the current provider as the default params
    const providerModels = groupedModels[value] || [];
    const filteredModels = providerModels.filter(m => m.worker_type === selectedWorkerType);
    if (filteredModels.length > 0) {
      const firstModel = filteredModels[0];
      if (firstModel?.params) {
        setParams(Array.isArray(firstModel.params) ? firstModel.params : [firstModel.params]);
      }
    }
  }

  async function onFinish(values: any) {
    if (!selectedProvider || !selectedWorkerType) return;

    const processFormValues = (formValues: any) => {
      const processed = { ...formValues };

      params?.forEach(param => {
        if (param.nested_fields && processed[param.param_name]) {
          const nestedValue = processed[param.param_name];
          // Make sure to keep all field values
          if (nestedValue.type) {
            const typeFields = param.nested_fields[nestedValue.type] || [];
            const fieldValues = {};

            // Collect values of all fields
            typeFields.forEach(field => {
              if (nestedValue[field.param_name] !== undefined) {
                fieldValues[field.param_name] = nestedValue[field.param_name];
              }
            });

            processed[param.param_name] = {
              ...fieldValues,
              type: nestedValue.type,
            };
          }
        }
      });

      return processed;
    };

    setLoading(true);
    try {
      const processedValues = processFormValues(values);
      const selectedModel = groupedModels[selectedProvider]?.find(m => m.model === processedValues.name);

      const params: StartModelParams = {
        host: selectedModel?.host || '',
        port: selectedModel?.port || 0,
        model: processedValues.name,
        worker_type: selectedWorkerType,
        params: processedValues,
      };

      const [, , data] = await apiInterceptors(createModel(params));
      if (data?.success) {
        message.success(t('start_model_success'));
        form.resetFields();
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
      <FormItem
        label='Worker Type'
        name='worker_type'
        rules={[{ required: true, message: t('worker_type_select_tips') }]}
      >
        <Select onChange={handleWorkerTypeChange} placeholder={t('model_select_worker_type')}>
          {WORKER_TYPES.map(type => (
            <Option key={type} value={type}>
              {type}
            </Option>
          ))}
        </Select>
      </FormItem>

      {selectedWorkerType && (
        <FormItem label='Provider' name='provider' rules={[{ required: true, message: t('provider_select_tips') }]}>
          <Select onChange={handleProviderChange} placeholder={t('model_select_provider')} value={selectedProvider}>
            {providers.map(provider => (
              <Option key={provider} value={provider}>
                {provider}
              </Option>
            ))}
          </Select>
        </FormItem>
      )}

      {selectedProvider && selectedWorkerType && params && (
        <>
          <FormItem
            label={t('model_deploy_name')}
            name='name'
            rules={[{ required: true, message: t('model_please_input_name') }]}
          >
            <AutoComplete
              style={{ width: '100%' }}
              placeholder={t('model_select_or_input_model')}
              options={groupedModels[selectedProvider]
                ?.filter(model => model.worker_type === selectedWorkerType)
                .map(model => ({
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

          <ConfigurableForm params={params.filter(p => p.param_name !== 'name')} form={form} />
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
