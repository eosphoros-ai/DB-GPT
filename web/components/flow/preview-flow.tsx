import { IFlowData } from '@/types/flow';
import { mapUnderlineToHump } from '@/utils/flow';
import React from 'react';
import ReactFlow, { Background } from 'reactflow';
import 'reactflow/dist/style.css';
import ButtonEdge from './button-edge';

const PreviewFlow: React.FC<{ flowData: IFlowData; minZoom?: number }> = ({ flowData, minZoom }) => {
  const data = mapUnderlineToHump(flowData);

  return (
    <ReactFlow
      nodes={data.nodes}
      edges={data.edges}
      edgeTypes={{ buttonedge: ButtonEdge }}
      fitView
      minZoom={minZoom || 0.1}
    >
      <Background color='#aaa' gap={16} />
    </ReactFlow>
  );
};

export default PreviewFlow;
