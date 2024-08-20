import { apiInterceptors, getAgents, getAppStrategy, getPromptList, getResourceType } from '@/client/api';
import { IAgent, IDetail } from '@/types/app';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Checkbox, Form, Space, Tooltip } from 'antd';
import cls from 'classnames';
import { concat } from 'lodash';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { agentIcon, resourceTypeIcon } from '../../config';
import DetailsCard from './DetailsCard';
import { useTranslation } from 'react-i18next';

interface AgentSelectProps {
  agents: IAgent[];
  selectedTab: string;
  setSelectedTab: React.Dispatch<React.SetStateAction<string>>;
  value?: any;
  onChange?: (value: any) => void;
}
// 自定义agent选择
const AgentSelect: React.FC<AgentSelectProps> = ({ value, onChange, agents, selectedTab, setSelectedTab }) => {
  return (
    <Checkbox.Group
      className="grid grid-cols-4 gap-4"
      onChange={(value: string[]) => {
        onChange?.(value);
      }}
      value={value}
    >
      {agents.map((item) => {
        return (
          <div
            className={`flex grow h-8 items-center px-3 border ${
              item.name === selectedTab ? 'border-[#0c75fc]' : 'border-[#d6d8da]'
            } rounded-md hover:border-[#0c75fc] cursor-pointer`}
            key={item.name}
            onClick={() => {
              setSelectedTab(item.name || '');
            }}
          >
            <Checkbox value={item.name} />
            <div className="flex items-center flex-1 justify-between">
              <div>
                <span className="ml-2 mr-1">{agentIcon[item.name || '']}</span>
                <span className="text-sm text-[rgba(0,10,26,0.68)] dark:text-[rgba(255,255,255,0.85)]">{item.label}</span>
              </div>
              <Tooltip title={item.desc}>
                <QuestionCircleOutlined className="text-sm" />
              </Tooltip>
            </div>
          </div>
        );
      })}
    </Checkbox.Group>
  );
};

const AutoPlan: React.FC<{
  initValue: any;
  updateData: (data: any) => void;
  classNames?: string;
}> = ({ initValue, updateData, classNames }) => {
  const { t, i18n } = useTranslation();
  const [form] = Form.useForm();
  const agentName = Form.useWatch('agent_name', form);
  // 选中的agent
  const [selectedTab, setSelectedTab] = useState<string>('');
  const details = useRef<IDetail[]>([]);
  const language = i18n.language === 'en';

  // 获取agents, strategy, sourceType;
  const { data, loading } = useRequest(async () => {
    const res = await Promise.all([apiInterceptors(getAgents()), apiInterceptors(getAppStrategy()), apiInterceptors(getResourceType())]);
    const [, agents] = res?.[0] || [];
    details.current =
      agents?.map((item) => {
        return {
          agent_name: item.name,
          llm_strategy: '',
          llm_strategy_value: '',
          prompt_template: '',
          resources: [],
        };
      }) || [];
    form.setFieldsValue({ agent_name: initValue?.map((item: any) => item.agent_name) });
    setSelectedTab(initValue?.map((item: any) => item.agent_name)?.[0] || agents?.[0]?.name || '');
    return res ?? [];
  });

  // 获取prompt提示语列表
  const { data: promptData } = useRequest(async () => {
    const [, res] = await apiInterceptors(
      getPromptList({
        page: 1,
        page_size: 100000,
      }),
    );
    return res ?? { items: [] };
  });

  // 模型策略options
  const modelStrategyOptions: any[] = useMemo(() => {
    const [, strategy] = data?.[1] || [];
    if (strategy?.length) {
      return strategy.map((item) => {
        return {
          label: language ? item.name : item.name_cn,
          value: item.value,
        };
      });
    }
    return [];
  }, [data]);

  // 资源类型options
  const resourceTypeOptions: Record<string, any>[] = useMemo(() => {
    const [, sourceType] = data?.[2] || [];
    if (sourceType?.length) {
      const formatterSourceType = sourceType.map((item) => {
        return {
          label: (
            <Space>
              {resourceTypeIcon[item]}
              {item}
            </Space>
          ),
          value: item,
        };
      });

      return concat(
        [
          {
            label: (
              <div className="flex items-center text-sm">
                {resourceTypeIcon['all']}
                <span className="ml-2 text-[rgba(0,10,26,0.68)] dark:text-[#ffffffD9]">{t('All')}</span>
              </div>
            ),
            value: 'all',
          },
        ],
        formatterSourceType,
      );
    }
    return [];
  }, [data]);

  // 实时返回数据给消费组件
  useEffect(() => {
    updateData([loading, details.current.filter((detail) => agentName?.includes(detail.agent_name))]);
  }, [loading, agentName, updateData]);

  return (
    <div className={cls(classNames)}>
      <Form form={form} style={{ width: '100%' }} labelCol={{ span: 4 }} wrapperCol={{ span: 20 }}>
        <Form.Item label={`${t('choose')} agent`} name="agent_name" required rules={[{ required: true, message: t('please_choose') + ' agent' }]}>
          <AgentSelect agents={data?.[0]?.[1] || []} selectedTab={selectedTab} setSelectedTab={setSelectedTab} />
        </Form.Item>
      </Form>
      {data?.[0]?.[1]?.map((item) => (
        <DetailsCard
          key={item.name}
          classNames={item.name === selectedTab ? 'block' : 'hidden'}
          updateData={(data: any) => {
            details.current = details.current.map((detail) => {
              if (detail.agent_name === data?.agent_name) {
                return {
                  ...detail,
                  ...data,
                };
              }
              return {
                ...detail,
              };
            });
            updateData([loading, details.current.filter((detail) => agentName?.includes(detail.agent_name))]);
          }}
          initValue={initValue}
          name={item.name}
          modelStrategyOptions={modelStrategyOptions}
          resourceTypeOptions={resourceTypeOptions}
          promptList={promptData?.items || []}
        />
      ))}
    </div>
  );
};
export default AutoPlan;
