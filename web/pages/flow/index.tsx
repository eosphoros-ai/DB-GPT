import { addFlow, apiInterceptors, getFlows } from '@/client/api';
import MyEmpty from '@/components/common/MyEmpty';
import MuiLoading from '@/components/common/loading';
import FlowCard from '@/components/flow/flow-card';
import { IFlow, IFlowUpdateParam } from '@/types/flow';
import { PlusOutlined } from '@ant-design/icons';
import { Button, Checkbox, Form, Input, Modal, message } from 'antd';
import Link from 'next/link';
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

type FormFields = Pick<IFlow, 'label' | 'name'>;

function Flow() {
  const { t } = useTranslation();

  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [flowList, setFlowList] = useState<Array<IFlow>>([]);
  const [deploy, setDeploy] = useState(false);

  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<Pick<IFlow, 'label' | 'name'>>();

  const copyFlowTemp = useRef<IFlow>();

  async function getFlowList() {
    setLoading(true);
    const [_, data] = await apiInterceptors(getFlows());
    setLoading(false);
    setFlowList(data?.items ?? []);
  }

  useEffect(() => {
    getFlowList();
  }, []);

  function updateFlowList(uid: string) {
    setFlowList((flows) => flows.filter((flow) => flow.uid !== uid));
  }

  const handleCopy = (flow: IFlow) => {
    copyFlowTemp.current = flow;
    form.setFieldValue('label', `${flow.label} Copy`);
    form.setFieldValue('name', `${flow.name}_copy`);
    setDeploy(false);
    setShowModal(true);
  };

  const onFinish = async (val: { name: string; label: string }) => {
    if (!copyFlowTemp.current) return;
    const { source, uid, dag_id, gmt_created, gmt_modified, state, ...params } = copyFlowTemp.current;
    const data: IFlowUpdateParam = {
      ...params,
      editable: true,
      state: deploy ? 'deployed' : 'developing',
      ...val,
    };
    const [err] = await apiInterceptors(addFlow(data));
    if (!err) {
      messageApi.success(t('save_flow_success'));
      setShowModal(false);
      getFlowList();
    }
  };

  return (
    <div className="relative p-4 md:p-6 min-h-full overflow-y-auto">
      {contextHolder}
      <MuiLoading visible={loading} />
      <div className="mb-4">
        <Link href="/flow/canvas">
          <Button type="primary" className="flex items-center" icon={<PlusOutlined />}>
            New AWEL Flow
          </Button>
        </Link>
      </div>
      <div className="flex flex-wrap gap-2 md:gap-4 justify-start items-stretch">
        {flowList.map((flow) => (
          <FlowCard key={flow.uid} flow={flow} deleteCallback={updateFlowList} onCopy={handleCopy} />
        ))}
        {flowList.length === 0 && <MyEmpty description="No flow found" />}
      </div>
      <Modal
        open={showModal}
        title="Copy AWEL Flow"
        onCancel={() => {
          setShowModal(false);
        }}
        footer={false}
      >
        <Form form={form} onFinish={onFinish} className="mt-6">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="label" label="Label" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Deploy">
            <Checkbox
              value={deploy}
              onChange={(e) => {
                const val = e.target.checked;
                setDeploy(val);
              }}
            />
          </Form.Item>
          <div className="flex justify-end">
            <Button type="primary" htmlType="submit">
              {t('Submit')}
            </Button>
          </div>
        </Form>
      </Modal>
    </div>
  );
}

export default Flow;
