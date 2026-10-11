import { apiInterceptors, postDbAdd, postDbEdit, postDbTestConnect } from '@/client/api';
import { ConfigurableParams } from '@/types/common';
import { DBOption, DBType } from '@/types/db';
import { Button, Form, Input, Select, message } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ConfigurableForm from '../common/configurable-form';

const { Option } = Select;
const FormItem = Form.Item;

interface DatabaseFormProps {
  onCancel: () => void;
  onSuccess: () => void;
  dbTypeList: DBOption[];
  editValue?: string;
  choiceDBType?: DBType;
  getFromRenderData?: ConfigurableParams[];
  dbNames?: string[];
  description?: string; // Add description prop
}

function DatabaseForm({
  onCancel,
  onSuccess,
  dbTypeList,
  editValue,
  choiceDBType,
  getFromRenderData,
  dbNames = [],
  description = '', // Default value for description
}: DatabaseFormProps) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [selectedType, setSelectedType] = useState<DBType | undefined>(choiceDBType);
  const [params, setParams] = useState<Array<ConfigurableParams> | null>(getFromRenderData || null);
  console.log('dbTypeList', dbTypeList);
  console.log('editValue', editValue);
  console.log('choiceDBType', choiceDBType);

  useEffect(() => {
    if (choiceDBType) {
      setSelectedType(choiceDBType);
    }
  }, [choiceDBType]);

  useEffect(() => {
    if (editValue && getFromRenderData) {
      setParams(getFromRenderData);
      // set description
      form.setFieldValue('description', description);
    }
  }, [editValue, getFromRenderData, description, form]);

  const handleTypeChange = (value: DBType) => {
    setSelectedType(value);
    form.resetFields(['params']);

    const selectedDBType = dbTypeList.find(type => type.value === value);
    if (selectedDBType?.parameters) {
      setParams(selectedDBType.parameters);
    }
  };

  const handleSubmit = async (formValues: any) => {
    try {
      setLoading(true);

      console.log('dbNames:', dbNames);

      // Check if database name is duplicated
      // if (!editValue && dbNames.includes(values.database)) {
      //   message.error(t('database_name_exists'));
      //   return;
      // }

      const { description, type, ...values } = formValues;

      const data = {
        type: selectedType,
        params: values,
        description: description || '',
      };

      // If in edit mode, add id
      if (editValue) {
        data.id = editValue;
      }

      console.log('Form submitted:', data);

      const [testErr] = await apiInterceptors(postDbTestConnect(data));
      if (testErr) return;
      const [err] = await apiInterceptors((editValue ? postDbEdit : postDbAdd)(data));
      if (err) {
        message.error(err.message);
        return;
      }
      message.success(t(editValue ? 'update_success' : 'create_success'));
      onSuccess?.();
    } catch (error) {
      console.error('Failed to submit form:', error);
      message.error(t(editValue ? 'update_failed' : 'create_failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form
      form={form}
      layout='vertical'
      onFinish={handleSubmit}
      initialValues={{
        type: selectedType,
      }}
    >
      <FormItem
        label={t('database_type')}
        name='type'
        rules={[{ required: true, message: t('please_select_database_type') }]}
      >
        <Select placeholder={t('select_database_type')} onChange={handleTypeChange} disabled={!!editValue}>
          {dbTypeList.map(type => (
            <Option key={type.value} value={type.value} disabled={type.disabled}>
              {type.label}
            </Option>
          ))}
        </Select>
      </FormItem>

      {params && <ConfigurableForm params={params} form={form} />}

      <FormItem label={t('description')} name='description'>
        <Input.TextArea rows={2} placeholder={t('input_description')} />
      </FormItem>

      <div className='flex justify-end space-x-4 mt-6'>
        <Button onClick={onCancel}>{t('cancel')}</Button>
        <Button type='primary' htmlType='submit' loading={loading}>
          {t('submit')}
        </Button>
      </div>
    </Form>
  );
}

export default DatabaseForm;
