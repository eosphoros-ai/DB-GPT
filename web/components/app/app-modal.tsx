import { IAgent } from '@/types/app';
import { Dropdown, Form, Input, Modal, Select, Space, Spin, Tabs } from 'antd';
import React, { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AddIcon from '../icons/add-icon';
import AgentPanel from './agent-panel';

type TargetKey = React.MouseEvent | React.KeyboardEvent | string;

type FieldType = {
  name: string;
  description: string;
  language: string;
  team_mode: string;
};

interface IProps {
  handleCancel: () => void;
  open: boolean;
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

export default function AppModal(props: IProps) {
  const { handleCancel, open } = props;
  const { t } = useTranslation();
  const [spinning, setSpinning] = useState<boolean>(false);
  const [agents, setAgents] = useState<IAgent[]>([]);
  const [activeKey, setActiveKey] = useState(initialItems[0].key);
  const [items, setItems] = useState(initialItems);
  const newTabIndex = useRef(0);

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

  const handleFinish = async (fieldsValue: FieldType) => {};

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
      <Modal title="add application" open={open} onCancel={handleCancel}>
        <Spin spinning={spinning}>
          <Form
            size="large"
            className="mt-4 h-[650px] overflow-auto"
            layout="vertical"
            initialValues={{ remember: true }}
            autoComplete="off"
            onFinish={handleFinish}
          >
            <Form.Item<FieldType> label={'App Name'} name="name" rules={[{ required: true, message: t('Please_input_the_name') }]}>
              <Input className="h-12" placeholder={t('Please_input_the_name')} />
            </Form.Item>
            <Form.Item<FieldType>
              label={t('Description')}
              name="description"
              rules={[{ required: true, message: t('Please_input_the_description') }]}
            >
              <Input className="h-12" placeholder={t('Please_input_the_description')} />
            </Form.Item>
            <Form.Item<FieldType> label={t('language')} name="language" rules={[{ required: true }]}>
              <Select className="h-12" placeholder={t('language_select_tips')} />
            </Form.Item>
            <Form.Item<FieldType> label={t('team_modal')} name="team_mode" rules={[{ required: true }]}>
              <Select className="h-12" placeholder={t('Please_input_the_description')} />
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
