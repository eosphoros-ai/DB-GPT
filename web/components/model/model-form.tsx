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

interface ModelFormProps {
  onCancel: () => void;
  onSuccess: () => void;
  // When both are provided, the form is opened with a fixed provider/worker
  // type (e.g. from the model config page) and only asks for model name + key.
  defaultProvider?: string;
  defaultWorkerType?: string;
  // Shared provider-level credentials. When present, the api key is inherited
  // from the provider and the form no longer asks for it.
  providerConfig?: { api_key?: string; api_base?: string };
}

function ModelForm({ onCancel, onSuccess, defaultProvider, defaultWorkerType, providerConfig }: ModelFormProps) {
  const { t } = useTranslation();
  const [_, setModels] = useState<Array<SupportModel> | null>([]);
  const [selectedWorkerType, setSelectedWorkerType] = useState<string | undefined>(defaultWorkerType);
  const [selectedProvider, setSelectedProvider] = useState<string | undefined>(defaultProvider);
  const [params, setParams] = useState<Array<ConfigurableParams> | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [form] = Form.useForm();

  const [groupedModels, setGroupedModels] = useState<{ [key: string]: SupportModel[] }>({});
  const [providers, setProviders] = useState<string[]>([]);

  const isPreset = Boolean(defaultWorkerType && defaultProvider);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When opened with a preset provider/worker type, apply the selection once
  // the supported models have loaded.
  useEffect(() => {
    if (!defaultWorkerType || !defaultProvider || Object.keys(groupedModels).length === 0) return;
    setSelectedWorkerType(defaultWorkerType);
    updateProvidersByWorkerType(defaultWorkerType);
    form.setFieldValue('worker_type', defaultWorkerType);
    applyProvider(defaultProvider, defaultWorkerType);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupedModels, defaultWorkerType, defaultProvider]);

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

  function applyProvider(provider: string, workerType: string | undefined) {
    setSelectedProvider(provider);
    form.setFieldValue('provider', provider);

    // Get the params of the first model that matches the worker_type under the
    // current provider as the default params.
    const providerModels = groupedModels[provider] || [];
    const filteredModels = providerModels.filter(m => m.worker_type === workerType);
    if (filteredModels.length > 0) {
      const firstModel = filteredModels[0];
      if (firstModel?.params) {
        setParams(Array.isArray(firstModel.params) ? firstModel.params : [firstModel.params]);
      }
    }
  }

  function handleProviderChange(value: string) {
    applyProvider(value, selectedWorkerType);
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
      const processedValues = {
        ...processFormValues(values),
        // provider is required by the backend even when it is preset and hidden
        provider: selectedProvider,
        // inherit shared provider credentials so the user doesn't re-enter them
        ...(providerConfig?.api_key ? { api_key: providerConfig.api_key } : {}),
        ...(providerConfig?.api_base ? { api_base: providerConfig.api_base } : {}),
      };
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

  // Simplify the config form: for API (proxy) providers only surface the api key,
  // leaving api_base / concurrency / verbosity etc. to their backend defaults.
  // Local providers keep their full parameter set.
  function getVisibleParams(): Array<ConfigurableParams> | null {
    if (!params) return null;
    const hasApiKey = params.some(p => p.param_name === 'api_key');
    // If the provider already carries a key, don't ask for it again.
    const apiKeySupplied = Boolean(providerConfig?.api_key);
    return params
      .filter(p => p.param_name !== 'name')
      .filter(p => (hasApiKey ? p.param_name === 'api_key' && !apiKeySupplied : true))
      .map(p => (p.param_name === 'api_key' ? { ...p, label: t('model_api_key') } : p));
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
      {!isPreset && (
        <>
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
        </>
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

          <ConfigurableForm params={getVisibleParams()} form={form} />
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
