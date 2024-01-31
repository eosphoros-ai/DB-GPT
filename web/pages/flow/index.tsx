import { apiInterceptors, getFlows } from '@/client/api';
import MuiLoading from '@/components/common/loading';
import FlowCard from '@/components/flow/flow-card';
import { IFlow } from '@/types/flow';
import { PlusOutlined } from '@ant-design/icons';
import { Button, Empty } from 'antd';
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
    <div className="relative p-4 md:p-6 bg-[#FAFAFA] dark:bg-transparent min-h-full overflow-y-auto">
      <MuiLoading visible={loading} />
      <div className="mb-4">
        <Link href="/flow/canvas">
          <Button type="primary" className="flex items-center" icon={<PlusOutlined />}>
            New AWEL Flow
          </Button>
        </Link>
      </div>
      <div className="min-h-[600px] flex flex-wrap gap-2 md:gap-4 justify-start items-start">
        {flowList.map((flow) => (
          <FlowCard key={flow.uid} flow={flow} deleteCallback={updateFlowList} />
        ))}
        {flowList.length === 0 && <Empty description="No flow found" />}
      </div>
    </div>
  );
}

export default Flow;
