/* eslint-disable react-hooks/exhaustive-deps */
import { Button, Form, Input, InputNumber, Modal, Select, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { apiInterceptors, postDbAdd, postDbEdit, postDbTestConnect } from '@/client/api';
import { DBOption, DBType, DbListResponse, PostDbParams } from '@/types/db';
import { isFileDb } from '@/pages/database';
import { useTranslation } from 'react-i18next';

type DBItem = DbListResponse[0];

interface Props {
  dbTypeList: DBOption[];
  open: boolean;
  choiceDBType?: DBType;
  editValue?: DBItem;
  dbNames: string[];
  onSuccess?: () => void;
  onClose?: () => void;
}

function FormDialog({ open, choiceDBType, dbTypeList, editValue, dbNames, onClose, onSuccess }: Props) {
  const [loading, setLoading] = useState(false);
  const { t } = useTranslation();
  const [form] = Form.useForm<DBItem>();
  const dbType = Form.useWatch('db_type', form);

  const fileDb = useMemo(() => isFileDb(dbTypeList, dbType), [dbTypeList, dbType]);

  useEffect(() => {
    if (choiceDBType) {
      form.setFieldValue('db_type', choiceDBType);
    }
  }, [choiceDBType]);

  useEffect(() => {
    if (editValue) {
      form.setFieldsValue({ ...editValue });
    }
  }, [editValue]);

  useEffect(() => {
    if (!open) {
      form.resetFields();
    }
  }, [open]);

  const onFinish = async (val: DBItem) => {
    const { db_host, db_path, db_port, ...params } = val;
    if (!editValue && dbNames.some((item) => item === params.db_name)) {
      message.error('The database already exists!');
      return;
    }
    const data: PostDbParams = {
      db_host: fileDb ? undefined : db_host,
      db_port: fileDb ? undefined : db_port,
      file_path: fileDb ? db_path : undefined,
      ...params,
    };
    setLoading(true);
    try {
      const [testErr] = await apiInterceptors(postDbTestConnect(data));
      if (testErr) return;
      const [err] = await apiInterceptors((editValue ? postDbEdit : postDbAdd)(data));
      if (err) {
        message.error(err.message);
        return;
      }
      message.success('success');
      onSuccess?.();
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const lockDBType = useMemo(() => !!editValue || !!choiceDBType, [editValue, choiceDBType]);

  return (
    <Modal open={open} width={400} title={editValue ? t('Edit') : t('create_database')} maskClosable={false} footer={null} onCancel={onClose}>
      <Form form={form} className="pt-2" labelCol={{ span: 6 }} labelAlign="left" onFinish={onFinish}>
        <Form.Item name="db_type" label="DB Type" className="mb-3" rules={[{ required: true }]}>
          <Select aria-readonly={lockDBType} disabled={lockDBType} options={dbTypeList} />
        </Form.Item>
        <Form.Item name="db_name" label="DB Name" className="mb-3" rules={[{ required: true }]}>
          <Input readOnly={!!editValue} disabled={!!editValue} />
        </Form.Item>
        {fileDb === true && (
          <Form.Item name="db_path" label="Path" className="mb-3" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        )}
        {fileDb === false && (
          <>
            <Form.Item name="db_user" label="Username" className="mb-3" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="db_pwd" label="Password" className="mb-3" rules={[{ required: true }]}>
              <Input type="password" />
            </Form.Item>
            <Form.Item name="db_host" label="Host" className="mb-3" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="db_port" label="Port" className="mb-3" rules={[{ required: true }]}>
              <InputNumber min={1} step={1} max={65535} />
            </Form.Item>
          </>
        )}

        <Form.Item name="comment" label="Remark" className="mb-3">
          <Input />
        </Form.Item>
        <Form.Item className="flex flex-row-reverse pt-1 mb-0">
          <Button htmlType="submit" type="primary" size="middle" className="mr-1" loading={loading}>
            Save
          </Button>
          <Button size="middle" onClick={onClose}>
            Cancel
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default FormDialog;
