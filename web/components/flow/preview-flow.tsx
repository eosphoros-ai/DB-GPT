import { IFlowData } from '@/types/flow';
import React from 'react';
import ReactFlow, { Background } from 'reactflow';
import ButtonEdge from './button-edge';
import { mapUnderlineToHump } from '@/utils/flow';
import 'reactflow/dist/style.css';

const PreviewFlow: React.FC<{ flowData: IFlowData; minZoom?: number }> = ({ flowData, minZoom }) => {
  const data = mapUnderlineToHump(flowData);

  return (
    <ReactFlow nodes={data.nodes} edges={data.edges} edgeTypes={{ buttonedge: ButtonEdge }} fitView minZoom={minZoom || 0.1}>
      <Background color="#aaa" gap={16} />
    </ReactFlow>
  );
};

export default PreviewFlow;
