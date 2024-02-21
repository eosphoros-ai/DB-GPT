import { apiInterceptors, getResource } from '@/client/api';
import { DeleteFilled } from '@ant-design/icons';
import { Button, Card, ConfigProvider, Input, Select, Switch } from 'antd';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface IProps {
  resourceTypeOptions: any[];
  updateResourcesByIndex: (data: any, index: number) => void;
  index: number;
  resource: any;
}

export default function ResourceCard(props: IProps) {
  const { resourceTypeOptions, updateResourcesByIndex, index, resource: editResource } = props;

  const { t } = useTranslation();

  const [resourceType, setResourceType] = useState<string>(editResource.type || resourceTypeOptions?.[0].label);
  const [resourceValueOptions, setResourceValueOptions] = useState<any[]>([]);
  const [resource, setResource] = useState<any>({
    name: editResource.name,
    type: editResource.type,
    value: editResource.value,
    is_dynamic: editResource.is_dynamic || false,
  });

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

  const handleDeleteResource = () => {
    updateResourcesByIndex(null, index);
  };

  useEffect(() => {
    fetchResource();
    updateResource(resource.type || resourceType, 'type');
  }, [resourceType]);

  useEffect(() => {
    updateResource(resourceValueOptions[0]?.label || editResource.value, 'value');
    setResource({ ...resource, value: resourceValueOptions[0]?.label || editResource.value });
  }, [resourceValueOptions]);

  return (
    <Card
      className="mb-3 dark:bg-[#232734] border-gray-200"
      title={`${t('resource')} ${index + 1}`}
      extra={
        <DeleteFilled
          className="text-[#ff1b2e] !text-lg"
          onClick={() => {
            handleDeleteResource();
          }}
        />
      }
    >
      <div className="flex-1">
        <div className="flex items-center  mb-6">
          <div className="font-bold mr-4 w-32 text-center">
            <span className="text-[#ff4d4f] font-normal">*</span>&nbsp;{t('resource_name')}:
          </div>
          <Input
            className="w-1/3"
            required
            value={resource.name}
            onInput={(e: React.ChangeEvent<HTMLInputElement>) => {
              updateResource(e.target.value, 'name');
            }}
          />
          <div className="flex items-center">
            <div className="font-bold w-32 text-center">{t('resource_dynamic')}</div>

            <Switch
              defaultChecked={editResource.is_dynamic || false}
              style={{ background: resource.is_dynamic ? '#1677ff' : '#ccc' }}
              onChange={(value) => {
                updateResource(value, 'is_dynamic');
              }}
            />
          </div>
        </div>
        <div className="flex mb-5  items-center">
          <div className="font-bold mr-4 w-32  text-center">{t('resource_type')}: </div>
          <Select
            className="w-1/3"
            options={resourceTypeOptions}
            value={resource.type || resourceTypeOptions?.[0]}
            onChange={(value) => {
              updateResource(value, 'type');
              handleChange(value);
            }}
          />
          <div className="font-bold w-32 text-center">{t('resource_value')}:</div>
          {resourceValueOptions?.length > 0 ? (
            <Select
              value={resource.value}
              className="flex-1"
              options={resourceValueOptions}
              onChange={(value) => {
                updateResource(value, 'value');
              }}
            />
          ) : (
            <Input
              className="flex-1"
              value={resource.value || editResource.value}
              onInput={(e: React.ChangeEvent<HTMLInputElement>) => {
                updateResource(e.target.value, 'value');
              }}
            />
          )}
        </div>
      </div>
    </Card>
  );
}
