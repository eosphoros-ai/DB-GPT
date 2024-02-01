import { apiInterceptors, getResource } from '@/client/api';
import { Button, Card, Input, Select } from 'antd';
import { log } from 'console';
import React, { useEffect, useState } from 'react';
import ResourceCard from './resource-card';
import { useTranslation } from 'react-i18next';

interface IProps {
  resourceTypes: any;
  updateDetailsByName: (name: string, data: any) => void;
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
  const { resourceTypes, updateDetailsByName, detail } = props;
  const { t } = useTranslation();

  const [resources, setResources] = useState<any>([]);
  const [agent, setAgent] = useState<any>({ ...detail });

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

  const handelAdd = () => {
    setResources([...resources, {}]);
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
      <Input className="mb-3" required />
      <div className="mb-3">LLM 使用策略</div>
      <Input disabled className="mb-3" value={'priority'} />
      <div className="mb-3">可用资源</div>
      {resources.map((_: any, index: number) => {
        return <ResourceCard updateResourcesByIndex={updateResourcesByIndex} resourceTypeOptions={resourceTypeOptions} />;
      })}
      <Button onClick={handelAdd}>{t('Add')}</Button>
    </div>
  );
}
