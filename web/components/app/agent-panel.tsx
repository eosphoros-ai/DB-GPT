import { apiInterceptors, getResource } from '@/client/api';
import { Button, Card, Divider, Input, Select } from 'antd';
import { log } from 'console';
import React, { useEffect, useState } from 'react';
import ResourceCard from './resource-card';
import { useTranslation } from 'react-i18next';

interface IProps {
  resourceTypes: any;
  updateDetailsByAgentKey: (key: string, data: any) => void;
  detail: any;
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
  const { resourceTypes, updateDetailsByAgentKey, detail } = props;
  const { t } = useTranslation();

  const [resources, setResources] = useState<any>([]);
  const [agent, setAgent] = useState<any>({ ...detail, resources: [] });

  const updateResourcesByIndex = (data: any, index: number) => {
    setResources((resources: any) => {
      const tempResources = [...resources];
      return tempResources.map((item: any, indey) => {
        if (index === indey) {
          return data;
        } else {
          return item;
        }
      });
    });
  };

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

  const resourceTypeOptions = resourceTypes?.map((item: string) => {
    return {
      label: item,
      value: item,
    };
  });

  return (
    <div>
      <div className="mb-3">prompt</div>
      <Input
        className="mb-5"
        required
        onChange={(e) => {
          updateAgent(e.target.value, 'agent_name');
        }}
      />
      <div className="mb-3">LLM 使用策略</div>
      <Input disabled className="mb-5" value={'priority'} />
      <div className="mb-3 text-lg font-bold">可用资源</div>
      {resources.map((_: any, index: number) => {
        return (
          <div key={index}>
            <ResourceCard key={index} index={index} updateResourcesByIndex={updateResourcesByIndex} resourceTypeOptions={resourceTypeOptions} />
            {index !== resources.length - 1 && <Divider />}
          </div>
        );
      })}
      <Button type="primary" className='mt-2' size='middle' onClick={handelAdd}>
        {t('add_resource')}
      </Button>
    </div>
  );
}