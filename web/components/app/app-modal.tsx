import { AgentParams, IAgent as IAgentParams, IApp, IDetail } from '@/types/app';
import { Dropdown, Form, Input, Modal, Select, Space, Spin, Tabs } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AddIcon from '../icons/add-icon';
import AgentPanel from './agent-panel';
import { addApp, apiInterceptors, getAgents, getResourceType, getTeamMode, updateApp } from '@/client/api';
import type { TabsProps } from 'antd';
import DagLayout from './dag-layout';
import { IFlow } from '@/types/flow';

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

type TeamModals = 'awel_layout' | 'singe_agent' | 'auto_plan';

export default function AppModal(props: IProps) {
  const { handleCancel, open, updateApps, type, app } = props;

  const { t } = useTranslation();
  const [spinning, setSpinning] = useState<boolean>(false);
  const [activeKey, setActiveKey] = useState<string>();
  const [teamModal, setTeamModal] = useState<{ label: string; value: string }[]>();
  const [agents, setAgents] = useState<TabsProps['items']>([]);
  const [dropItems, setDropItems] = useState<IAgent[]>([]);
  const [details, setDetails] = useState<IDetail[]>([...(app?.details || [])]);
  const [flow, setFlow] = useState<IFlow>();
  const [resourceTypes, setResourceTypes] = useState<string[]>();
  const [curTeamModal, setCurTeamModal] = useState<TeamModals>(app.team_modal || 'auto_plan');

  const [form] = Form.useForm();

  const languageOptions = [
    { value: 'zh', label: t('Chinese') },
    { value: 'en', label: t('English') },
  ];

  const onChange = (newActiveKey: string) => {
    setActiveKey(newActiveKey);
  };

  const createApp = async (app: IApp) => {
    await apiInterceptors(type === 'add' ? addApp(app) : updateApp(app));
    await updateApps();
  };

  const initApp = async () => {
    const appDetails = app.details;
    const [_, resourceType] = await apiInterceptors(getResourceType());

    if (appDetails?.length > 0) {
      setAgents(
        appDetails?.map((item: AgentParams) => {
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
      data
        .map((agent) => {
          return {
            label: agent.name,
            key: agent.name,
            onClick: () => {
              add(agent);
            },
            agent,
          };
        })
        .filter((item) => {
          if (!app.details || app.details?.length === 0) {
            return item;
          }
          return app?.details?.every((detail: AgentParams) => detail.agent_name !== item.label);
        }),
    );
  };

  const handleFlowsChange = (data: IFlow) => {
    setFlow(data);
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

  useEffect(() => {
    setCurTeamModal(app.team_mode || 'auto_plan');
  }, [app]);

  const updateDetailsByAgentKey = (key: string, data: IDetail) => {
    setDetails((details: IDetail[]) => {
      return details.map((detail: IDetail) => {
        return key === (detail.agent_name || detail.key) ? data : detail;
      });
    });
  };

  const add = async (tabBar: IAgentParams) => {
    const newActiveKey = tabBar.name;
    const [_, data] = await apiInterceptors(getResourceType());

    setActiveKey(newActiveKey);

    setDetails((details: IDetail[]) => {
      return [...details, { key: newActiveKey, name: '', llm_strategy: 'priority' }];
    });

    setAgents((items: any) => {
      return [
        ...items,
        {
          label: newActiveKey,
          children: (
            <AgentPanel
              detail={{ key: newActiveKey, llm_strategy: 'default', agent_name: newActiveKey, prompt_template: '', llm_strategy_value: null }}
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
    setDetails((details: IDetail[]) => {
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
    };
    if (type === 'edit') {
      data.app_code = app.app_code;
    }

    if (data.team_mode !== 'awel_layout') {
      data.details = details;
    } else {
      const tempFlow = { ...flow };
      delete tempFlow.flow_data;
      data.team_context = tempFlow;
    }

    try {
      await createApp(data);
    } catch (error) {
      return;
    }

    setSpinning(false);
    handleCancel();
  };

  const handleTeamModalChange = (value: TeamModals) => {
    setCurTeamModal(value);
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
        title={type === 'edit' ? t('edit_application') : t('add_application')}
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
            className="mt-4 max-h-[70vh] overflow-auto h-[90vh]"
            layout="horizontal"
            labelAlign="left"
            labelCol={{ span: 4 }}
            initialValues={{
              app_name: app.app_name,
              app_describe: app.app_describe,
              language: app.language || languageOptions[0].value,
              team_mode: app.team_mode || 'auto_plan',
            }}
            autoComplete="off"
            onFinish={handleSubmit}
          >
            <Form.Item<FieldType> label={t('app_name')} name="app_name" rules={[{ required: true, message: t('Please_input_the_name') }]}>
              <Input placeholder={t('Please_input_the_name')} />
            </Form.Item>
            <Form.Item<FieldType>
              label={t('Description')}
              name="app_describe"
              rules={[{ required: true, message: t('Please_input_the_description') }]}
            >
              <Input.TextArea rows={3} placeholder={t('Please_input_the_description')} />
            </Form.Item>
            <div className="flex w-full">
              <Form.Item<FieldType> labelCol={{ span: 7 }} label={t('language')} name="language" className="w-1/2" rules={[{ required: true }]}>
                <Select className="w-2/3 ml-4" placeholder={t('language_select_tips')} options={languageOptions} />
              </Form.Item>
              <Form.Item<FieldType> label={t('team_modal')} name="team_mode" className="w-1/2" labelCol={{ span: 6 }} rules={[{ required: true }]}>
                <Select
                  defaultValue={app.team_mode || 'auto_plan'}
                  className="ml-4 w-72"
                  onChange={handleTeamModalChange}
                  placeholder={t('Please_input_the_work_modal')}
                  options={teamModal}
                />
              </Form.Item>
            </div>
            {curTeamModal !== 'awel_layout' ? (
              <>
                <div className="mb-5">{t('Agents')}</div>
                <Tabs addIcon={renderAddIcon()} type="editable-card" onChange={onChange} activeKey={activeKey} onEdit={onEdit} items={agents} />
              </>
            ) : (
              <DagLayout onFlowsChange={handleFlowsChange} teamContext={app.team_context} />
            )}
          </Form>
        </Spin>
      </Modal>
    </div>
  );
}
