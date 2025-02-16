/* eslint-disable react-hooks/exhaustive-deps */
import { addOmcDB, apiInterceptors, getSupportDBList, postDbAdd, postDbEdit, postDbTestConnect } from '@/client/api';
import { isFileDb } from '@/pages/construct/database';
import { DBOption, DBType, DbListResponse, PostDbParams } from '@/types/db';
import { useDebounceFn } from 'ahooks';
import { Button, Form, Input, Modal, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type DBItem = DbListResponse[0] & { db_arn?: string };

interface Props {
  dbTypeList: DBOption[];
  open: boolean;
  choiceDBType?: DBType;
  editValue?: DBItem;
  dbNames: string[];
  onSuccess?: () => void;
  onClose?: () => void;
}

function FormDialog({
  open,
  choiceDBType,
  dbTypeList,
  getFromRenderData,
  editValue,
  dbNames,
  onClose,
  onSuccess,
}: Props) {
  const [loading, setLoading] = useState(false);
  const { t } = useTranslation();
  const [form] = Form.useForm<DBItem>();
  const dbType = Form.useWatch('db_type', form);
  const [omcDBList, setOmcDBList] = useState([]);
  const [fromDefault, setFromDefault] = useState({});
  const [omcListLoading, setOmcListLoading] = useState(false);
  const fileDb = useMemo(() => isFileDb(dbTypeList, dbType), [dbTypeList, dbType]);

  useEffect(() => {
    if (choiceDBType) {
      form.setFieldValue('db_type', choiceDBType);
    }
  }, [choiceDBType]);

  useEffect(() => {
    console.log(getFromRenderData);
    let obj = {}
    for (let index = 0; index < getFromRenderData.length; index++) {
      const element = getFromRenderData[index];
      obj[element.param_name] = element.default_value
    }
    setFromDefault(obj)
  }, [getFromRenderData]);

  useEffect(() => {
    if (editValue) {
      form.setFieldsValue({ ...editValue });
      if (editValue.db_type === 'omc') {
        form.setFieldValue('db_arn', editValue.db_path);
      }
    }
  }, [editValue]);

  useEffect(() => {
    if (!open) {
      form.resetFields();
    }
  }, [open]);

  const onFinish = async (val: DBItem) => {
    const { db_host, db_path, db_port, db_type, ...params } = val;

    for(const key in val){
      if (!isNaN(val[key])) {
        val[key] = +val[key]
      }
    }
    setLoading(true);

    if (db_type === 'omc') {
      const item = omcDBList?.find((item: any) => item.arn === val.db_name) as any;

      try {
        const [err] = await apiInterceptors(
          addOmcDB({
            db_type: 'omc',
            file_path: val.db_arn || '',
            comment: val.comment,
            db_name: item?.dbName || val.db_name,
          }),
        );
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
    }
    if (!editValue && dbNames.some(item => item === params.db_name)) {
      message.error('The database already exists!');
      return;
    }
    // const data: PostDbParams = {
    //   db_host: fileDb ? undefined : db_host,
    //   db_port: fileDb ? undefined : db_port,
    //   db_type: db_type,
    //   file_path: fileDb ? db_path : undefined,
    //   ...params,
    // };
    const data = {
      type: choiceDBType,
      params: val,
    }
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

  const { run: fetchOmcList } = useDebounceFn(
    async (name: string) => {
      setOmcListLoading(true);
      const [_, data = []] = (await apiInterceptors(getSupportDBList(name))) as any;
      setOmcListLoading(false);

      setOmcDBList(data.map((item: any) => ({ ...item, label: item.dbName, value: item.arn })));
    },
    {
      wait: 500,
    },
  );

  const lockDBType = useMemo(() => !!editValue || !!choiceDBType, [editValue, choiceDBType]);
  return (
    <Modal
      open={open}
      width={800}
      title={editValue ? t('Edit') + ' - ' + choiceDBType : t('create_database')  + ' - '  + choiceDBType}
      maskClosable={false}
      footer={null}
      
      onCancel={onClose}
    >
      <Form form={form} initialValues={fromDefault} className='pt-2' labelCol={{ span: 6 }} labelAlign='left' onFinish={onFinish}>
        {getFromRenderData.map(item => (
          <Form.Item name={item.param_name} label={item.label} className='mb-6' rules={[{ required: item.required }]}>
            <Input defaultValue={item.default_value} value={item.default_value} readOnly={!!editValue}  />
        
          </Form.Item>
        
        ))}
  
        {/* <Form.Item name='db_name' label='DB Name' className='mb-3' rules={[{ required: true }]}>
        </Form.Item> */}
        {/* {form.getFieldValue('db_type') === 'omc' ? (
          <Form.Item name='db_name' label='DB Name' className='mb-6' rules={[{ required: true }]}>
            <Select
              optionRender={(option, { index }) => {
                const item = omcDBList[index] as any;
                return (
                  <div key={option.value} className='flex flex-col'>
                    <span className='text-[18px]'>{item?.dbName}</span>
                    <span>
                      <span>env: </span>
                      <span className='text-gray-500'>{item.env}</span>
                    </span>
                    <span>
                      <span>account: </span>
                      <span className='text-gray-500'>{item.account}</span>
                    </span>
                    <span>
                      <span>searchName: </span>
                      <Tooltip title={item.searchName}>
                        <span className='text-gray-500'>{item.searchName}</span>
                      </Tooltip>
                    </span>
                  </div>
                );
              }}
              notFoundContent={omcListLoading ? <Spin size='small' /> : null}
              showSearch
              options={omcDBList}
              onSearch={fetchOmcList}
              onSelect={searchName => {
                const item = omcDBList?.find((item: any) => item.value === searchName) as any;
                form.setFieldsValue({
                  db_arn: item?.arn,
                });
              }}
            />
          </Form.Item>
        ) : (
          <Form.Item name='db_name' label='DB Name' className='mb-3' rules={[{ required: true }]}>
            <Input readOnly={!!editValue} disabled={!!editValue} />
          </Form.Item>
        )}
        {fileDb === true && (
          <Form.Item name='db_path' label='Path' className='mb-6' rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        )}
        {fileDb === false && form.getFieldValue('db_type') !== 'omc' && (
          <>
            <Form.Item name='db_user' label='Username' className='mb-6' rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name='db_pwd' label='Password' className='mb-6' rules={[{ required: false }]}>
              <Input type='password' />
            </Form.Item>
            <Form.Item name='db_host' label='Host' className='mb-6' rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name='db_port' label='Port' className='mb-6' rules={[{ required: true }]}>
              <InputNumber min={1} step={1} max={65535} />
            </Form.Item>
          </>
        )}
        {form.getFieldValue('db_type') === 'omc' && (
          <Form.Item name='db_arn' label='Arn' className='mb-6' rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        )}
        <Form.Item name='comment' label='Remark' className='mb-6'>
          <Input />
        </Form.Item> */}
        <Form.Item className='flex flex-row-reverse pt-1 mb-0'>
          <Button htmlType='submit' type='primary' size='middle' className='mr-1' loading={loading}>
            Save
          </Button>
          <Button size='middle' onClick={onClose}>
            Cancel
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}

export default FormDialog;
