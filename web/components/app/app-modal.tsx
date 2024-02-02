import { IAgent as IAgentParams } from '@/types/app';
import { Dropdown, Form, Input, Modal, Select, Space, Spin, Tabs } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AddIcon from '../icons/add-icon';
import AgentPanel from './agent-panel';
import { addApp, apiInterceptors, getAgents, getResourceType, getTeamMode, updateApp } from '@/client/api';
import type { TabsProps } from 'antd';

type TargetKey = string;

type FieldType = {
  app_name: string;
  app_describe: string;
  language: string;
  team_mode: string;
};

type IAgent = {
  label: string;
  children?: React.ReactNode;
  onClick?: () => void;
  key: number | string;
};

interface IProps {
  handleCancel: () => void;
  open: boolean;
  updateApps: () => void;
  type: string;
  app?: any;
}

const languageOptions = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: '英文' },
];

export default function AppModal(props: IProps) {
  const { handleCancel, open, updateApps, type, app } = props;

  const { t } = useTranslation();
  const [spinning, setSpinning] = useState<boolean>(false);
  const [activeKey, setActiveKey] = useState<string>();
  const [teamModal, setTeamModal] = useState<{ label: string; value: string }[]>();
  const [agents, setAgents] = useState<TabsProps['items']>([]);
  const [dropItems, setDropItems] = useState<IAgent[]>([]);
  const [details, setDetails] = useState<any>([...(app?.details || [])]);
  const [initialValue, setInitialValue] = useState<any>({ app_name: '', app_describe: '', language: '', team_mode: '' });
  const [resourceTypes, setResourceTypes] = useState<any>();

  const [form] = Form.useForm();

  const onChange = (newActiveKey: string) => {
    setActiveKey(newActiveKey);
  };

  const createApp = async (app: any) => {
    await apiInterceptors(type === 'add' ? addApp(app) : updateApp(app));
    await updateApps();
  };

  const initApp = async () => {
    const appDetails = app.details;
    const [_, resourceType] = await apiInterceptors(getResourceType());

    setInitialValue({ app_name: app.app_name, app_describe: app.app_describe, language: app.language, team_mode: app.team_mode });
    if (appDetails?.length > 0) {
      setAgents(
        appDetails?.map((item: any) => {
          return {
            label: item?.agent_name,
            children: (
              <AgentPanel
                editResources={type === 'edit' && item.resources}
                detail={{
                  key: item?.agent_name,
                  llm_strategy: item?.llm_strategy,
                  agent_name: item?.agent_name,
                  prompt_template: item?.prompt_template,
                  llm_strategy_value: item?.llm_strategy_value,
                }}
                updateDetailsByAgentKey={updateDetailsByAgentKey}
                resourceTypes={resourceType}
              />
            ),
            key: item?.agent_name,
          };
        }),
      );
    }
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
    if (!data) {
      return null;
    }

    setDropItems(
      data.map((agent) => {
        return {
          label: agent.name,
          key: agent.name,
          onClick: () => {
            add(agent);
          },
          agent,
        };
      }),
    );
  };

  const fetchResourceType = async () => {
    const [_, data] = await apiInterceptors(getResourceType());
    if (data) {
      setResourceTypes(data);
    }
  };

  useEffect(() => {
    fetchTeamModal();
    fetchAgent();
    fetchResourceType();
  }, []);

  useEffect(() => {
    type === 'edit' && initApp();
  }, [resourceTypes]);

  const updateDetailsByAgentKey = (key: string, data: any) => {
    setDetails((details: any) => {
      return details.map((detail: any) => {
        return key === (detail.agent_name || detail.key) ? data : detail;
      });
    });
  };

  const add = async (tabBar: IAgentParams) => {
    const newActiveKey = tabBar.name;
    const [_, data] = await apiInterceptors(getResourceType());

    setActiveKey(newActiveKey);

    setDetails((details: any) => {
      return [...details, { key: newActiveKey, name: '', llm_strategy: 'priority' }];
    });

    setAgents((items: any) => {
      return [
        ...items,
        {
          label: newActiveKey,
          children: (
            <AgentPanel
              detail={{ key: newActiveKey, llm_strategy: 'default', agent_name: newActiveKey, prompt_template: '', llm_strategy_value: '' }}
              updateDetailsByAgentKey={updateDetailsByAgentKey}
              resourceTypes={data}
            />
          ),
          key: newActiveKey,
        },
      ];
    });

    setDropItems((items) => {
      return items.filter((item) => item.key !== tabBar.name);
    });
  };

  const remove = (targetKey: TargetKey) => {
    let newActiveKey = activeKey;
    let lastIndex = -1;

    if (!agents) {
      return null;
    }

    agents.forEach((item, i) => {
      if (item.key === targetKey) {
        lastIndex = i - 1;
      }
    });

    const newPanes = agents.filter((item) => item.key !== targetKey);
    if (newPanes.length && newActiveKey === targetKey) {
      if (lastIndex >= 0) {
        newActiveKey = newPanes[lastIndex].key;
      } else {
        newActiveKey = newPanes[0].key;
      }
    }
    setDetails((details: any) => {
      return details?.filter((detail: any) => {
        return (detail.agent_name || detail.key) !== targetKey;
      });
    });

    setAgents(newPanes);
    setActiveKey(newActiveKey);
    setDropItems((items: any) => {
      return [
        ...items,
        {
          label: targetKey,
          key: targetKey,
          onClick: () => {
            add({ name: targetKey, describe: '', system_message: '' });
          },
        },
      ];
    });
  };

  const onEdit = (targetKey: any, action: 'add' | 'remove') => {
    if (action === 'add') {
      // add();
    } else {
      remove(targetKey);
    }
  };

  const handleSubmit = async () => {
    const isValidate = await form.validateFields();

    if (!isValidate) {
      return;
    }
    setSpinning(true);

    const data = {
      ...form.getFieldsValue(),
      details: details,
    };
    if (type === 'edit') {
      data.app_code = app.app_code;
    }

    await createApp(data);

    setSpinning(false);
    handleCancel();
  };

  const renderAddIcon = () => {
    return (
      <Dropdown menu={{ items: dropItems }} trigger={['click']}>
        <a className="h-8 flex items-center" onClick={(e) => e.preventDefault()}>
          <Space>
            <AddIcon />
          </Space>
        </a>
      </Dropdown>
    );
  };

  return (
    <div>
      <Modal
        okText={t('Submit')}
        title={type === 'edit' ? 'edit application' : 'add application'}
        open={open}
        width={'65%'}
        onCancel={handleCancel}
        onOk={handleSubmit}
        destroyOnClose={true}
      >
        <Spin spinning={spinning}>
          <Form
            form={form}
            preserve={false}
            size="large"
            className="mt-4 max-h-[70vh] overflow-auto"
            layout="horizontal"
            labelAlign="left"
            labelCol={{ span: 4 }}
            initialValues={{ app_name: app.app_name, app_describe: app.app_describe, language: app.language, team_mode: app.team_mode }}
            autoComplete="off"
            onFinish={handleSubmit}
          >
            <Form.Item<FieldType> label={'App Name'} name="app_name" rules={[{ required: true, message: t('Please_input_the_name') }]}>
              <Input placeholder={t('Please_input_the_name')} />
            </Form.Item>
            <Form.Item<FieldType>
              label={t('Description')}
              name="app_describe"
              rules={[{ required: true, message: t('Please_input_the_description') }]}
            >
              <Input.TextArea rows={3} placeholder={t('Please_input_the_description')} />
            </Form.Item>
            <Form.Item<FieldType> label={t('language')} initialValue={languageOptions[0].value} name="language" rules={[{ required: true }]}>
              <Select placeholder={t('language_select_tips')} options={languageOptions} />
            </Form.Item>
            <Form.Item<FieldType>
              label={t('team_modal')}
              name="team_mode"
              rules={[{ required: true }]}
              initialValue={teamModal && teamModal[0].value}
            >
              <Select placeholder={t('Please_input_the_work_modal')} options={teamModal} />
            </Form.Item>
            <div className='mb-5 text-lg font-bold"'>Agents</div>
            <Tabs addIcon={renderAddIcon()} type="editable-card" onChange={onChange} activeKey={activeKey} onEdit={onEdit} items={agents} />
          </Form>
        </Spin>
      </Modal>
    </div>
  );
}
