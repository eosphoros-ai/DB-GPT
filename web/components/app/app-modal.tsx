import { IAgent, ITeamModal } from '@/types/app';
import { Dropdown, Form, Input, Modal, Select, Space, Spin, Tabs } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AddIcon from '../icons/add-icon';
import AgentPanel from './agent-panel';
import { addApp, apiInterceptors, getAgents, getTeamMode } from '@/client/api';

type TargetKey = React.MouseEvent | React.KeyboardEvent | string;

type FieldType = {
  app_name: string;
  app_describe: string;
  language: string;
  team_mode: string;
};

interface IProps {
  handleCancel: () => void;
  open: boolean;
  updateApps: () => void;
}

const initialItems = [
  { label: 'agent 1', children: <AgentPanel />, key: '1' },
  { label: 'agent 2', children: <AgentPanel />, key: '2' },
  {
    label: 'agent 3',
    children: <AgentPanel />,
    key: '3',
  },
];

const dropItems: any = [
  {
    label: 'agent1 ',
    key: '0',
    onClick: () => {},
  },
  {
    label: 'agent2',
    key: '1',
    onClick: () => {},
  },
  {
    label: 'agent3',
    key: '3',
    onClick: () => {},
  },
];

const languageOptions = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: '英文' },
];

export default function AppModal(props: IProps) {
  const { handleCancel, open, updateApps } = props;
  const { t } = useTranslation();
  const [spinning, setSpinning] = useState<boolean>(false);
  const [activeKey, setActiveKey] = useState(initialItems[0].key);
  const [teamModal, setTeamModal] = useState<{ label: string; value: string }[]>();
  const [items, setItems] = useState(initialItems);
  const newTabIndex = useRef(0);

  const [form] = Form.useForm();

  const onChange = (newActiveKey: string) => {
    setActiveKey(newActiveKey);
  };

  const add = (tabBar: any) => {
    const newActiveKey = `newTab${newTabIndex.current++}`;

    setItems((items: any) => {
      return [...items, { label: 'New Tab', children: 'Content of new Tab', key: newActiveKey }];
    });
    setActiveKey(newActiveKey);
  };

  const createApp = async (app: any) => {
    await apiInterceptors(addApp(app));
    await updateApps();
  };

  const fetchTeamModal = async () => {
    const [_, data] = await apiInterceptors(getTeamMode());
    if (!data) return null;

    const teamModalOptions = data.map((item) => {
      return { value: item, label: item };
    });
    setTeamModal(teamModalOptions);
  };

  const fetchAgent = async () => {
    const [_, data] = await apiInterceptors(getAgents());
    console.log('1111agent', data);
  };

  useEffect(() => {
    fetchTeamModal();
    fetchAgent();
  }, []);

  dropItems?.forEach((item: any) => {
    item.onClick = () => {
      add(item);
    };
  });

  const remove = (targetKey: TargetKey) => {
    let newActiveKey = activeKey;
    let lastIndex = -1;
    items.forEach((item, i) => {
      if (item.key === targetKey) {
        lastIndex = i - 1;
      }
    });
    const newPanes = items.filter((item) => item.key !== targetKey);
    if (newPanes.length && newActiveKey === targetKey) {
      if (lastIndex >= 0) {
        newActiveKey = newPanes[lastIndex].key;
      } else {
        newActiveKey = newPanes[0].key;
      }
    }
    setItems(newPanes);
    setActiveKey(newActiveKey);
  };

  const onEdit = (targetKey: React.MouseEvent | React.KeyboardEvent | string, action: 'add' | 'remove') => {
    if (action === 'add') {
      // add();
    } else {
      remove(targetKey);
    }
  };

  const handleSubmit = async() => {
    setSpinning(true);
    const data = {
      ...form.getFieldsValue(),
      details: [],
    };
    await createApp(data);
    setSpinning(false);
    handleCancel();
  };

  const renderAddIcon = () => {
    return (
      <Dropdown menu={{ items: dropItems }} trigger={['click']}>
        <a onClick={(e) => e.preventDefault()}>
          <Space>
            <AddIcon />
          </Space>
        </a>
      </Dropdown>
    );
  };

  return (
    <div>
      <Modal title="add application" open={open} onCancel={handleCancel} onOk={handleSubmit}>
        <Spin spinning={spinning}>
          <Form
            form={form}
            size="large"
            className="mt-4 h-[650px] overflow-auto"
            layout="vertical"
            initialValues={{ remember: true }}
            autoComplete="off"
            onFinish={handleSubmit}
          >
            <Form.Item<FieldType> label={'App Name'} name="app_name" rules={[{ required: true, message: t('Please_input_the_name') }]}>
              <Input className="h-12" placeholder={t('Please_input_the_name')} />
            </Form.Item>
            <Form.Item<FieldType>
              label={t('Description')}
              name="app_describe"
              rules={[{ required: true, message: t('Please_input_the_description') }]}
            >
              <Input className="h-12" placeholder={t('Please_input_the_description')} />
            </Form.Item>
            <Form.Item<FieldType> label={t('language')} name="language" rules={[{ required: true }]}>
              <Select className="h-12" placeholder={t('language_select_tips')} options={languageOptions} />
            </Form.Item>
            <Form.Item<FieldType> label={t('team_modal')} name="team_mode" rules={[{ required: true }]}>
              <Select className="h-12" placeholder={t('Please_input_the_description')} options={teamModal} />
            </Form.Item>
            <div>
              <div className="mb-5">Agent</div>
            </div>
            <Tabs addIcon={renderAddIcon()} type="editable-card" onChange={onChange} activeKey={activeKey} onEdit={onEdit} items={items} />
          </Form>
        </Spin>
      </Modal>
    </div>
  );
}
