import { apiInterceptors, getUsableModels } from '@/client/api';
import { createBenchmarkTask } from '@/client/api/models_evaluation';
import { createBenchmarkTaskRequest } from '@/types/models_evaluation';
import { useRequest } from 'ahooks';
import { Form, Input, InputNumber, Modal, Select, Slider, message } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

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

  // 获取模型列表
  const { loading: modelLoading } = useRequest(
    async () => {
      const [_, data] = await apiInterceptors(getUsableModels());
      return data || [];
    },
    {
      onSuccess: data => {
        const options = data.map((item: string) => ({
          label: item,
          value: item,
        }));
        setModelOptions(options);
      },
      onError: error => {
        message.error(t('get_model_list_failed') + ': ' + error.message);
      },
    },
  );

  // 创建评测任务
  const { loading: submitLoading, run: submitEvaluation } = useRequest(
    async (values: any) => {
      // 构造评测任务参数
      const params: createBenchmarkTaskRequest = {
        scene_value: values.scene_value,
        model_list: values.model_list,
        temperature: values.temperature,
        max_tokens: values.max_tokens,
      };

      const [_, data] = await apiInterceptors(createBenchmarkTask(params));
      return data;
    },
    {
      manual: true,
      onSuccess: () => {
        message.success(t('create_evaluation_success'));
        form.resetFields();
        onOk?.(); // 触发外部的onOk回调，用于刷新列表
        onCancel();
      },
      onError: error => {
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
          temperature: 0.2,
          max_tokens: 1024,
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
          rules={[{ required: true, message: t('please_input_max_new_tokens') }]}
        >
          <InputNumber min={1} max={32768} style={{ width: '100%' }} placeholder={t('please_input_max_new_tokens')} />
        </Form.Item>
      </Form>
    </Modal>
  );
};
