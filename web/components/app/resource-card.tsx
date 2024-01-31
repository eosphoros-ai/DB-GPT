import { apiInterceptors, getResource } from '@/client/api';
import { Card, Input, Select } from 'antd';
import React, { useEffect, useState } from 'react';

interface IProps {
  resourceTypeOptions: any[];
  updateResourcesByIndex: (data: any, index: number) => void;
}

export default function ResourceCard(props: IProps) {
  const { resourceTypeOptions, updateResourcesByIndex } = props;

  const [resourceType, setResourceType] = useState<string>(resourceTypeOptions[0].key);

  const fetchResource = async () => {
    const [_, data] = await apiInterceptors(getResource({ type: resourceType }));
  };

  const handleChange = (value: string) => {
    setResourceType(value);
  };

  useEffect(() => {
    fetchResource();
  }, [resourceType]);

  return (
    <Card>
      <Input className="mb-3" required />
      <Select defaultValue={resourceTypeOptions[0]} className="h-12 w-1/2" options={resourceTypeOptions} onChange={handleChange} />
      <Select defaultValue={resourceTypeOptions[0]} className="h-12 w-1/2" options={resourceTypeOptions} onChange={handleChange} />
      <Input className="mb-3" required />
      <Select defaultValue={resourceTypeOptions[0]} className="h-12 w-1/2" options={resourceTypeOptions} onChange={handleChange} />
    </Card>
  );
}
