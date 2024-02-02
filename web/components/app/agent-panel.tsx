import { apiInterceptors, getAppStrategy, getResource } from '@/client/api';
import { Button, Card, Divider, Input, Select } from 'antd';
import { log } from 'console';
import React, { useEffect, useMemo, useState } from 'react';
import ResourceCard from './resource-card';
import { useTranslation } from 'react-i18next';

interface IProps {
  resourceTypes: any;
  updateDetailsByAgentKey: (key: string, data: any) => void;
  detail: any;
  editResources?: any;
}

/**
 * 
 *  "type": "internet",
    "name": "panda",
    "introduce": "大熊猫简介",
    "value": "https://baike.baidu.com/item/%E5%A4%A7%E7%86%8A%E7%8C%AB/34935",
    "is_dynamic": false
 */

export default function AgentPanel(props: IProps) {
  const { resourceTypes, updateDetailsByAgentKey, detail, editResources } = props;
  const { t } = useTranslation();

  const [resources, setResources] = useState<any>([...(editResources ?? [])]);
  const [agent, setAgent] = useState<any>({ ...detail, resources: [] });
  const [strategyOptions, setStrategyOptions] = useState<any>([]);

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

  useEffect(() => {
    getStrategy();
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
      <div className="flex items-center mb-6">
        <div className="mr-2 w-16 text-center">prompt:</div>
        <Input
          required
          className='mr-6 w-1/3'
          value={agent.prompt_template}
          onChange={(e) => {
            updateAgent(e.target.value, 'prompt_template');
          }}
        />
        <div className="fmr-2">LLM 使用策略:</div>
        <Select
          value={agent.llm_strategy}
          options={strategyOptions}
          className='w-1/3'
          onChange={(value) => {
            updateAgent(value, 'llm_strategy');
          }}
        />
      </div>
      <div className="mb-3 text-lg font-bold">可用资源</div>
      {resources.map((resource: any, index: number) => {
        return (
          <div key={index}>
            <ResourceCard
              resource={resource}
              key={index}
              index={index}
              updateResourcesByIndex={updateResourcesByIndex}
              resourceTypeOptions={resourceTypeOptions}
            />
            {index !== resources.length - 1 && <Divider />}
          </div>
        );
      })}
      <Button type="primary" className="mt-2" size="middle" onClick={handelAdd}>
        {t('add_resource')}
      </Button>
    </div>
  );
}
