import React, { Ref, forwardRef, useEffect, useState } from 'react';
import { Form, Input, Spin, Select, FormInstance } from 'antd';
import { useTranslation } from 'react-i18next';
import { IPrompt } from '@/types/prompt';

interface IProps {
  prompt?: IPrompt;
  onFinish: (prompt: IPrompt) => void;
  scenes?: Array<Record<string, string>>;
}

export default forwardRef(function PromptForm(props: IProps, ref: Ref<FormInstance<any>> | undefined) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const { prompt, onFinish, scenes } = props;
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (prompt) {
      form.setFieldsValue(prompt);
    }
  }, []);

  const submit = async () => {
    const values = form.getFieldsValue();
    setLoading(true);
    await onFinish(values);
    setLoading(false);
  };

  return (
    <Spin spinning={loading}>
      <Form form={form} ref={ref} name={`prompt-item-${prompt?.prompt_name || 'new'}`} layout="vertical" className="mt-4" onFinish={submit}>
        <Form.Item name="chat_scene" label={t('Prompt_Info_Scene')} rules={[{ required: true, message: t('Please_Input') + t('Prompt_Info_Scene') }]}>
          <Select options={scenes}></Select>
        </Form.Item>
        <Form.Item
          name="sub_chat_scene"
          label={t('Prompt_Info_Sub_Scene')}
          rules={[{ required: true, message: t('Please_Input') + t('Prompt_Info_Sub_Scene') }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="prompt_name" label={t('Prompt_Info_Name')} rules={[{ required: true, message: t('Please_Input') + t('Prompt_Info_Name') }]}>
          <Input disabled={!!prompt} />
        </Form.Item>
        <Form.Item
          name="content"
          label={t('Prompt_Info_Content')}
          rules={[{ required: true, message: t('Please_Input') + t('Prompt_Info_Content') }]}
        >
          <Input.TextArea rows={6} />
        </Form.Item>
      </Form>
    </Spin>
  );
});
