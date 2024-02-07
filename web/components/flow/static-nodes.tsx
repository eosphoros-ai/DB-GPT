import { IFlowNode } from '@/types/flow';
import { Avatar, Empty, List } from 'antd';
import React, { DragEvent } from 'react';
import { useTranslation } from 'react-i18next';

const StaticNodes: React.FC<{ nodes: IFlowNode[] }> = ({ nodes }) => {
  const { t } = useTranslation();

  function onDragStart(event: DragEvent, node: IFlowNode) {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(node));
    event.dataTransfer.effectAllowed = 'move';
  }

  if (nodes?.length > 0) {
    return (
      <List
        className="overflow-hidden overflow-y-auto w-full"
        itemLayout="horizontal"
        dataSource={nodes}
        renderItem={(node) => (
          <List.Item
            className="cursor-move hover:bg-[#F1F5F9] dark:hover:bg-theme-dark p-0 py-2"
            draggable
            onDragStart={(event) => onDragStart(event, node)}
          >
            <List.Item.Meta
              className="flex items-center justify-center"
              avatar={<Avatar src={'/icons/node/vis.png'} size={'large'} />}
              title={<p className="line-clamp-1 font-medium">{node.label}</p>}
              description={<p className="line-clamp-2">{node.description}</p>}
            />
          </List.Item>
        )}
      />
    );
  } else {
    return <Empty className="px-2" description={t('no_node')} />;
  }
};

export default StaticNodes;
