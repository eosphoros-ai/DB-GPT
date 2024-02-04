import React, { useEffect, useState } from 'react';
import PreviewFlow from '../flow/preview-flow';
import { apiInterceptors, getFlows } from '@/client/api';

export default function DagLayout() {
  const [flows, setFlows] = useState<any>();
  const fetchFlows = async () => {
    const [_, data] = await apiInterceptors(getFlows());
    if (data) {
      console.log(data);

      setFlows(data.items);
    }
  };

  useEffect(() => {
    fetchFlows();
  }, []);
  // return <PreviewFlow flowData={flows} />;
  return <div>react flows</div>;
}
