import { apiInterceptors, getResource } from '@/client/api';
import { Card, Input, Select, Switch } from 'antd';
import React, { useEffect, useState } from 'react';

interface IProps {
  resourceTypeOptions: any[];
  updateResourcesByIndex: (data: any, index: number) => void;
  index: number;
}

export default function ResourceCard(props: IProps) {
  const { resourceTypeOptions, updateResourcesByIndex, index } = props;

  const [resourceType, setResourceType] = useState<string>(resourceTypeOptions[0].label);
  const [resourceValueOptions, setResourceValueOptions] = useState<any[]>([]);
  const [resource, setResource] = useState<any>({ name: '', type: resourceTypeOptions[0].label, introduce: '', value: '', is_dynamic: false });

  const fetchResource = async () => {
    const [_, data] = await apiInterceptors(getResource({ type: resourceType }));
    if (data) {
      setResourceValueOptions(
        data?.map((item) => {
          return { label: item, value: item };
        }),
      );
    } else {
      setResourceValueOptions([]);
    }
  };

  const handleChange = (value: string) => {
    setResourceType(value);
  };

  const updateResource = (value: any, type: string) => {
    const tempResource = resource;

    tempResource[type] = value;
    setResource(tempResource);
    updateResourcesByIndex(tempResource, index);
  };

  useEffect(() => {
    fetchResource();
  }, [resourceType]);

  useEffect(() => {
    setResource({ ...resource, value: resourceValueOptions[0]?.label });
  }, [resourceValueOptions]);

  return (
    <Card>
      <div>
        <div className="mb-2 font-bold">资源名</div>
        <Input
          className="mb-5 w-1/2"
          required
          onInput={(e: React.ChangeEvent<HTMLInputElement>) => {
            updateResource(e.target.value, 'name');
          }}
        />
      </div>
      <div>
        <div className="mb-2 font-bold">描述</div>
        <Input
          className="mb-5 w-11/12"
          onInput={(e: React.ChangeEvent<HTMLInputElement>) => {
            updateResource(e.target.value, 'introduce');
          }}
        />
      </div>
      <div className="flex mb-5">
        <div className="w-1/2">
          <div className="mb-2 font-bold">资源类型</div>
          <Select
            defaultValue={resourceTypeOptions[0]}
            className="h-12 w-5/6"
            options={resourceTypeOptions}
            onChange={(value) => {
              updateResource(value, 'type');
              handleChange(value);
            }}
          />
        </div>
        <div className="w-1/2">
          <div className="mb-2 font-bold">参数</div>
          {resourceValueOptions?.length > 0 ? (
            <Select
              value={resource.value}
              className="h-12 w-5/6"
              options={resourceValueOptions}
              onChange={(value) => {
                updateResource(value, 'value');
              }}
            />
          ) : (
            <Input
              className="mb-5 w-11/12"
              onInput={(e: React.ChangeEvent<HTMLInputElement>) => {
                updateResource(e.target.value, 'value');
              }}
            />
          )}
        </div>
      </div>
      <div className="mb-2 font-bold">动态</div>
      <Switch
        autoFocus
        className="mb-5"
        onChange={(value) => {
          updateResource(value, 'is_dynamic');
        }}
      />
    </Card>
  );
}
