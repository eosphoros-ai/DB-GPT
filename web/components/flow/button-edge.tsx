import React from 'react';
import { getBezierPath, EdgeProps, BaseEdge, useReactFlow } from 'reactflow';

const ButtonEdge: React.FC<EdgeProps> = ({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style = {}, data, markerEnd }) => {
  const [edgePath, edgeCenterX, edgeCenterY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  const reactFlow = useReactFlow();

  function onEdgeClick(event: React.MouseEvent, id: string) {
    event.stopPropagation();
    reactFlow.setEdges(reactFlow.getEdges().filter((edge) => edge.id !== id));
  }
  return (
    <>
      <BaseEdge id={id} style={style} path={edgePath} markerEnd={markerEnd} />
      <foreignObject
        width={40}
        height={40}
        x={edgeCenterX - 40 / 2}
        y={edgeCenterY - 40 / 2}
        className="bg-transparent w-10 h-10 relative"
        requiredExtensions="http://www.w3.org/1999/xhtml"
      >
        <button
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-stone-400 dark:bg-zinc-700 cursor-pointer text-sm"
          onClick={(event) => onEdgeClick(event, id)}
        >
          ×
        </button>
      </foreignObject>
    </>
  );
};

export default ButtonEdge;
