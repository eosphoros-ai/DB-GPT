/* eslint-disable react-hooks/exhaustive-deps */
import { addOmcDB, apiInterceptors, getSupportDBList, postDbAdd, postDbEdit, postDbTestConnect } from '@/client/api';
import { isFileDb } from '@/pages/construct/database';
import { DBOption, DBType, DbListResponse, PostDbParams } from '@/types/db';
import { useDebounceFn } from 'ahooks';
import { Button, Form, Input,Select, Modal, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type DBItem = DbListResponse[0] & { db_arn?: string };
const { Option } = Select;

interface Props {
  dbTypeList: DBOption[];
  open: boolean;
  choiceDBType?: DBType;
  editValue?: DBItem;
  dbNames: string[];
  dbTypeData: any[];
  getFromRenderData: any[];
  onSuccess?: () => void;
  onClose?: () => void;
}

let renderFromList = [] as any[]
let modalTitle = ''
function FormDialog({
  open,
  choiceDBType,
  dbTypeList,
  getFromRenderData,
  editValue,
  dbTypeData,
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

 


  // useEffect(() => {
  //   if (editValue) {
  //     form.setFieldsValue({ ...editValue });
  //     if (editValue.db_type === 'omc') {
  //       form.setFieldValue('db_arn', editValue.db_path);
  //     }
  //   }
  // }, [editValue]);


  useEffect(() => {
    if (!open) {
      form.resetFields();
    }
    
    if (editValue) {
      modalTitle = t('Edit') + ' - ' + choiceDBType
    }else{
      modalTitle = t('create_database') + ' - ' + choiceDBType
    }
    if (dbTypeData && dbTypeData.length > 0) {
      modalTitle = t('create_database')
    }

    renderFromList = getFromRenderData || []

    setFromDefaultData()
  }, [open]);

  const selectDBType = (val: string) => {
    console.log(val);
    for (let index = 0; index < dbTypeData.length; index++) {
      const element = dbTypeData[index];
      if (element.value === val) {
        renderFromList = element.parameters
        break
      }
    }
    setFromDefaultData()
  };
  const setFromDefaultData = ()=>{
    let obj = {} as any
    for (let index = 0; index < renderFromList.length; index++) {
      const element = renderFromList[index];
      if (editValue) {
        obj[element.param_name] = element.default_value
      }else{
        if (element.required) {
          obj[element.param_name] = ''
        }
      }
    }
    setFromDefault(obj)
    form.setFieldsValue(obj);
  }
  const onFinish = async (val: any) => {
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
    let dataType = ''
    if (val.type && !choiceDBType) {
      dataType = JSON.parse(JSON.stringify(val.type))
    }
    delete val.type
    const data = {
      type: choiceDBType || dataType,
      params: val,
    }
    if (editValue) {
      data.id = editValue
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
      title={modalTitle}
      maskClosable={false}
      footer={null}
      onCancel={onClose}
    >
      <Form form={form} initialValues={fromDefault} className='pt-2' labelCol={{ span: 6 }} labelAlign='left' onFinish={onFinish}>
      {dbTypeData && dbTypeData.length > 0 ? (
            <Form.Item name='type' label='数据源类型：' className='mb-6'>
              <Select onChange={selectDBType} placeholder="请选择数据源类型">
                {dbTypeData.map(item=>(
                  <Option value={item.value}>{item.label}</Option>
                ))}
            </Select>
            </Form.Item>
          ) :''}
        {renderFromList.map(item => (
         
          <Form.Item name={item.param_name} label={item.label} className='mb-6' rules={[{ required: item.required }]}>
            <Input defaultValue={item.default_value}   />
          </Form.Item>
        ))}
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
