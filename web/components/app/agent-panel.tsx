import { apiInterceptors, getAppStrategy, getAppStrategyValues, getResource } from '@/client/api';
import { Button, Input, Select } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import ResourceCard from './resource-card';
import { useTranslation } from 'react-i18next';

interface IProps {
  resourceTypes: any;
  updateDetailsByAgentKey: (key: string, data: any) => void;
  detail: any;
  editResources?: any;
}

export default function AgentPanel(props: IProps) {
  const { resourceTypes, updateDetailsByAgentKey, detail, editResources } = props;
  const { t } = useTranslation();

  const [resources, setResources] = useState<any>([...(editResources ?? [])]);
  const [agent, setAgent] = useState<any>({ ...detail, resources: [] });
  const [strategyOptions, setStrategyOptions] = useState<any>([]);
  const [strategyValueOptions, setStrategyValueOptions] = useState<any>([]);

  const updateResourcesByIndex = (data: any, index: number) => {
    setResources((resources: any) => {
      const tempResources = [...resources];
      if (!data) {
        return tempResources.filter((_: any, indey) => index !== indey);
      }

      return tempResources.map((item: any, indey) => {
        if (index === indey) {
          return data;
        } else {
          return item;
        }
      });
    });
  };

  const getStrategy = async () => {
    const [_, data] = await apiInterceptors(getAppStrategy());
    if (data) {
      setStrategyOptions(data?.map((item) => ({ label: item, value: item })));
    }
  };

  const getStrategyValues = async (type: string) => {
    const [_, data] = await apiInterceptors(getAppStrategyValues(type));
    if (data) {
      setStrategyValueOptions(data.map((item) => ({ label: item, value: item })) ?? []);
    }
  };

  const formatStrategyValue = (value: string) => {
    return !value ? [] : value.split(',');
  };

  useEffect(() => {
    getStrategy();
    getStrategyValues(detail.llm_strategy);
  }, []);

  useEffect(() => {
    updateAgent(resources, 'resources');
  }, [resources]);

  const updateAgent = (data: any, type: string) => {
    const tempAgent = { ...agent };
    tempAgent[type] = data;

    setAgent(tempAgent);

    updateDetailsByAgentKey(detail.key, tempAgent);
  };

  const handelAdd = () => {
    setResources([...resources, { name: '', type: '', introduce: '', value: '', is_dynamic: '' }]);
  };

  const resourceTypeOptions = useMemo(() => {
    return resourceTypes?.map((item: string) => {
      return {
        label: item,
        value: item,
      };
    });
  }, [resourceTypes]);

  return (
    <div>
      <div className="flex items-center mb-6 mt-6">
        <div className="mr-2 w-16 text-center">{t('Prompt')}:</div>
        <Input
          required
          className="mr-6 w-1/4"
          value={agent.prompt_template}
          onChange={(e) => {
            updateAgent(e.target.value, 'prompt_template');
          }}
        />
        <div className="mr-2">{t('LLM_strategy')}:</div>
        <Select
          value={agent.llm_strategy}
          options={strategyOptions}
          className="w-1/6 mr-6"
          onChange={(value) => {
            updateAgent(value, 'llm_strategy');
            getStrategyValues(value);
          }}
        />
        {strategyValueOptions && strategyValueOptions.length > 0 && (
          <>
            <div className="mr-2">{t('LLM_strategy_value')}:</div>
            <Select
              value={formatStrategyValue(agent.llm_strategy_value)}
              className="w-1/4"
              mode="multiple"
              options={strategyValueOptions}
              onChange={(value) => {
                if (!value || value?.length === 0) {
                  updateAgent(null, 'llm_strategy_value');
                  return null;
                }

                const curValue = value.reduce((pre: string, cur: string, index: number) => {
                  if (index === 0) {
                    return cur;
                  } else {
                    return `${pre},${cur}`;
                  }
                }, '');

                updateAgent(curValue, 'llm_strategy_value');
              }}
            />
          </>
        )}
      </div>
      <div className="mb-3 text-lg font-bold">{t('available_resources')}</div>
      {resources.map((resource: any, index: number) => {
        return (
          <ResourceCard
            resource={resource}
            key={index}
            index={index}
            updateResourcesByIndex={updateResourcesByIndex}
            resourceTypeOptions={resourceTypeOptions}
          />
        );
      })}
      <Button type="primary" className="mt-2" size="middle" onClick={handelAdd}>
        {t('add_resource')}
      </Button>
    </div>
  );
}
