import { apiInterceptors, getUsableModels } from '@/client/api';
import { createBenchmarkTask } from '@/client/api/models_evaluation';
import { createBenchmarkTaskRequest } from '@/types/models_evaluation';
import { useRequest } from 'ahooks';
import { Form, Input, InputNumber, Modal, Radio, Select, Slider, message } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

const { TextArea } = Input;

interface Props {
  open: boolean;
  onCancel: () => void;
  onOk?: () => void;
}

export const NewEvaluationModal = (props: Props) => {
  const { open, onCancel, onOk } = props;
  const [form] = Form.useForm();
  const { t } = useTranslation();
  const [modelOptions, setModelOptions] = useState<{ label: string; value: string }[]>([]);
  const [evaluationType, setEvaluationType] = useState<'LLM' | 'AGENT'>('LLM');
  const [parseStrategy, setParseStrategy] = useState<'DIRECT' | 'JSON_PATH'>('JSON_PATH');

  // 获取模型列表
  const { loading: modelLoading } = useRequest(
    async () => {
      const [_, data] = await apiInterceptors(getUsableModels());
      return data || [];
    },
    {
      onSuccess: (data: string[]) => {
        const options = data.map((item: string) => ({
          label: item,
          value: item,
        }));
        setModelOptions(options);
      },
      onError: (error: any) => {
        message.error(t('get_model_list_failed') + ': ' + error.message);
      },
    },
  );

  // 创建评测任务
  const { loading: submitLoading, run: submitEvaluation } = useRequest(
    async (values: any) => {
      // 构造评测任务参数
      if (values.evaluation_type === 'LLM') {
        const params: createBenchmarkTaskRequest = {
          scene_value: values.scene_value,
          model_list: values.model_list,
          temperature: values.temperature,
          max_tokens: values.max_tokens,
          benchmark_type: values.evaluation_type,
        };

        const [_, data] = await apiInterceptors(createBenchmarkTask(params));
        return data;
      } else if (values.evaluation_type === 'AGENT') {
        let parsedHeaders = {};
        let parsedMapping = {};

        // 解析JSON字符串，提供错误处理
        try {
          if (values.headers) {
            parsedHeaders = JSON.parse(values.headers);
          }
        } catch (_error) {
          throw new Error('Header信息格式不正确，请输入有效的JSON格式');
        }

        try {
          if (values.parse_strategy === 'JSON_PATH' && values.response_mapping) {
            parsedMapping = JSON.parse(values.response_mapping);
          }
        } catch (_error) {
          throw new Error('Response Mapping配置格式不正确，请输入有效的JSON格式');
        }

        // 构造Agent评测参数，使用Agent专有字段
        const agentParams: createBenchmarkTaskRequest = {
          scene_value: values.scene_value,
          benchmark_type: values.evaluation_type,
          api_url: values.api_url,
          headers: parsedHeaders,
          parse_strategy: values.parse_strategy,
          response_mapping: parsedMapping,
          http_method: values.http_method || 'POST',
          timeout: values.timeout || 300,
        };

        const [__, agentData] = await apiInterceptors(createBenchmarkTask(agentParams));
        return agentData;
      }
    },
    {
      manual: true,
      onSuccess: () => {
        message.success(t('create_evaluation_success'));
        form.resetFields();
        setEvaluationType('LLM'); // 重置评测类型
        setParseStrategy('JSON_PATH'); // 重置解析策略
        onOk?.(); // 触发外部的onOk回调，用于刷新列表
        onCancel();
      },
      onError: (error: any) => {
        message.error(t('create_evaluation_failed') + ': ' + error.message);
      },
    },
  );

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      await submitEvaluation(values);
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    setEvaluationType('LLM');
    setParseStrategy('JSON_PATH');
    onCancel();
  };

  return (
    <Modal
      title={t('new_evaluation_task')}
      open={open}
      onOk={handleOk}
      onCancel={handleCancel}
      confirmLoading={submitLoading}
      width={600}
    >
      <Form
        form={form}
        layout='vertical'
        requiredMark={false}
        initialValues={{
          temperature: 0.6,
          evaluation_type: 'LLM',
          parse_strategy: 'JSON_PATH',
          http_method: 'POST',
          timeout: 300,
        }}
      >
        <Form.Item
          label={t('task_name')}
          name='scene_value'
          rules={[{ required: true, message: t('please_input_task_name') }]}
        >
          <Input placeholder={t('please_input_task_name')} />
        </Form.Item>

        <Form.Item
          label={t('evaluation_type')}
          name='evaluation_type'
          rules={[{ required: true, message: t('please_select_evaluation_type') }]}
        >
          <Radio.Group value={evaluationType} onChange={(e: any) => setEvaluationType(e.target.value)}>
            <Radio value='LLM'>{t('evaluate_model')}</Radio>
            <Radio value='AGENT'>{t('evaluate_agent')}</Radio>
          </Radio.Group>
        </Form.Item>

        {/* 模型评测相关输入框 */}
        {evaluationType === 'LLM' && (
          <>
            <Form.Item
              label={t('models_to_evaluate')}
              name='model_list'
              rules={[
                { required: true, message: t('please_select_models_to_evaluate') },
                { type: 'array', min: 1, message: t('please_select_at_least_one_model') },
              ]}
            >
              <Select
                mode='multiple'
                placeholder={t('please_select_models_to_evaluate')}
                options={modelOptions}
                loading={modelLoading}
                showSearch
                optionFilterProp='label'
                allowClear
              />
            </Form.Item>

            <Form.Item
              label={t('temperature')}
              name='temperature'
              rules={[{ required: true, message: t('please_input_temperature') }]}
            >
              <Slider
                min={0}
                max={1}
                step={0.1}
                marks={{
                  0: '0',
                  0.5: '0.5',
                  1: '1',
                }}
              />
            </Form.Item>

            <Form.Item
              label={t('max_new_tokens')}
              name='max_tokens'
              rules={[{ required: false, message: t('please_input_max_new_tokens') }]}
            >
              <InputNumber
                min={1}
                max={32768}
                style={{ width: '100%' }}
                placeholder={t('please_input_max_new_tokens')}
              />
            </Form.Item>
          </>
        )}

        {/* Agent评测相关输入框 */}
        {evaluationType === 'AGENT' && (
          <>
            <Form.Item
              label={t('api_url')}
              name='api_url'
              rules={[
                { required: true, message: t('please_input_api_url') },
                { type: 'url', message: t('please_input_valid_url') },
              ]}
            >
              <Input placeholder={t('api_url_placeholder')} />
            </Form.Item>

            <Form.Item
              label={t('http_method')}
              name='http_method'
              rules={[{ required: true, message: t('please_select_http_method') }]}
            >
              <Select placeholder={t('please_select_http_method')}>
                <Select.Option value='GET'>GET</Select.Option>
                <Select.Option value='POST'>POST</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item
              label={t('header_info')}
              name='headers'
              rules={[{ required: false, message: t('please_input_header_info') }]}
            >
              <TextArea rows={4} placeholder={t('header_info_placeholder')} />
            </Form.Item>

            <Form.Item
              label={t('parse_strategy')}
              name='parse_strategy'
              rules={[{ required: true, message: t('please_select_parse_strategy') }]}
            >
              <Select
                value={parseStrategy}
                onChange={value => setParseStrategy(value)}
                placeholder={t('please_select_parse_strategy')}
              >
                <Select.Option value='DIRECT'>{t('parse_strategy_direct')}</Select.Option>
                <Select.Option value='JSON_PATH'>{t('parse_strategy_json_path')}</Select.Option>
              </Select>
            </Form.Item>

            {parseStrategy === 'JSON_PATH' && (
              <Form.Item
                label={t('response_mapping')}
                name='response_mapping'
                rules={[{ required: true, message: t('please_input_response_mapping') }]}
              >
                <TextArea rows={4} placeholder={t('response_mapping_placeholder')} />
              </Form.Item>
            )}

            <Form.Item
              label={t('api_timeout')}
              name='timeout'
              rules={[
                { required: true, message: t('please_input_api_timeout') },
                { type: 'number', min: 1, max: 2000, message: t('timeout_range_validation') },
              ]}
            >
              <InputNumber min={1} max={300000} style={{ width: '100%' }} placeholder={t('api_timeout_placeholder')} />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  );
};
