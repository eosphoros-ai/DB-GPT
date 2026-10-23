import React from 'react';
import { EdgeProps, getStraightPath } from 'reactflow';

/**
 * A straight vertical edge with a "+" button in the middle; clicking it asks
 * the editor to insert a node between the two endpoints.
 */
const InsertEdge: React.FC<EdgeProps> = ({ sourceX, sourceY, targetX, targetY, data }) => {
  const [path] = getStraightPath({ sourceX, sourceY, targetX, targetY });
  const midY = (sourceY + targetY) / 2;
  return (
    <>
      <path d={path} fill='none' className='stroke-gray-300 dark:stroke-gray-600' strokeWidth={1.5} />
      <foreignObject x={sourceX - 9} y={midY - 9} width={18} height={18} className='overflow-visible'>
        <button
          onClick={event => {
            event.stopPropagation();
            data?.onInsert?.(data?.insertAt);
          }}
          className='w-[18px] h-[18px] rounded-full bg-white dark:bg-[#2a2c31] border border-gray-300 dark:border-gray-600 text-gray-400 hover:border-blue-500 hover:text-blue-500 text-[11px] leading-none flex items-center justify-center shadow-sm transition-colors'
          title='+'
        >
          +
        </button>
      </foreignObject>
    </>
  );
};

export default InsertEdge;
