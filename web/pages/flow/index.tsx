import { apiInterceptors, getFlows } from '@/client/api';
import MyEmpty from '@/components/common/MyEmpty';
import MuiLoading from '@/components/common/loading';
import FlowCard from '@/components/flow/flow-card';
import { IFlow } from '@/types/flow';
import { PlusOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import Link from 'next/link';
import React, { useEffect, useState } from 'react';

function Flow() {
  const [loading, setLoading] = useState(false);
  const [flowList, setFlowList] = useState<Array<IFlow>>([]);

  async function getFlowList() {
    setLoading(true);
    const [_, data] = await apiInterceptors(getFlows());
    setLoading(false);
    setFlowList(data?.items ?? []);
  }

  useEffect(() => {
    getFlowList();
  }, []);

  function updateFlowList(uid: string) {
    setFlowList((flows) => flows.filter((flow) => flow.uid !== uid));
  }

  return (
    <div className="relative p-4 md:p-6 min-h-full overflow-y-auto">
      <MuiLoading visible={loading} />
      <div className="mb-4">
        <Link href="/flow/canvas">
          <Button type="primary" className="flex items-center" icon={<PlusOutlined />}>
            New AWEL Flow
          </Button>
        </Link>
      </div>
      <div className="flex flex-wrap gap-2 md:gap-4 justify-start items-stretch">
        {flowList.map((flow) => (
          <FlowCard key={flow.uid} flow={flow} deleteCallback={updateFlowList} />
        ))}
        {flowList.length === 0 && <MyEmpty description="No flow found" />}
      </div>
    </div>
  );
}

export default Flow;
