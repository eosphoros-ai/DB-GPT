import React, { useEffect, useState } from 'react';
import PreviewFlow from '../flow/preview-flow';
import { apiInterceptors, getFlows } from '@/client/api';
import { IFlow } from '@/types/flow';
import { Select } from 'antd';
import Link from 'next/link';
import { t } from 'i18next';

interface IProps {
  onFlowsChange: (data: any) => void;
  teamContext: any;
}

export default function DagLayout(props: IProps) {
  const { onFlowsChange, teamContext } = props;
  const [flows, setFlows] = useState<IFlow[]>();
  const [flowsOptions, setFlowsOptions] = useState<any>();
  const [curFlow, setCurFlow] = useState<IFlow>();
  const fetchFlows = async () => {
    const [_, data] = await apiInterceptors(getFlows());
    if (data) {
      setFlowsOptions(data?.items?.map((item: IFlow) => ({ label: item.name, value: item.name })));
      setFlows(data.items);
      onFlowsChange(data?.items[0]);
    }
  };

  const handleFlowsChange = (value: string) => {
    setCurFlow(flows?.find((item) => value === item.name));
    onFlowsChange(flows?.find((item) => value === item.name));
  };

  useEffect(() => {
    fetchFlows();
  }, []);

  useEffect(() => {
    setCurFlow(flows?.find((item) => teamContext?.name === item.name) || flows?.[0]);
  }, [teamContext, flows]);

  return (
    <div className="w-full h-[300px]">
      <div className="mr-24 mb-4 mt-2">Flows:</div>
      <div className="flex items-center mb-6">
        <Select onChange={handleFlowsChange} value={curFlow?.name || flowsOptions?.[0]?.value} className="w-1/4" options={flowsOptions}></Select>
        <Link href="/flow/canvas/" className="ml-6">
          {t('edit_new_applications')}
        </Link>
        <div className="text-gray-500 ml-16">{curFlow?.description}</div>
      </div>
      {curFlow && (
        <div className="w-full h-full border-[0.5px] border-dark-gray">
          <PreviewFlow flowData={curFlow?.flow_data} />
        </div>
      )}
    </div>
  );
}
