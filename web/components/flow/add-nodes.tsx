import { apiInterceptors, getFlowNodes } from '@/client/api';
import { IFlowNode } from '@/types/flow';
import { PlusOutlined } from '@ant-design/icons';
import { Avatar, Badge, Button, Collapse, CollapseProps, Divider, Empty, Input, List, Popover } from 'antd';
import React, { DragEvent, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const { Search } = Input;

const AddNodes: React.FC = () => {
  const { t } = useTranslation();
  const [nodes, setNodes] = useState<Array<IFlowNode>>([]);
  const [operators, setOperators] = useState<Array<IFlowNode>>([]);
  const [resources, setResources] = useState<Array<IFlowNode>>([]);

  useEffect(() => {
    getNodes();
  }, []);

  async function getNodes() {
    const [_, data] = await apiInterceptors(getFlowNodes());
    if (data && data.length > 0) {
      setNodes(data);
      groupNodes(data);
    }
  }

  function groupNodes(data: IFlowNode[]) {
    // show operator nodes first, then show resource nodes
    setOperators((data || []).filter((node) => node.flow_type === 'operator'));
    setResources((data || []).filter((node) => node.flow_type === 'resource'));
  }

  const items: CollapseProps['items'] = useMemo(
    () => [
      {
        key: 'operator',
        label: 'Operator',
        children: renderNodes(operators),
        extra: <Badge showZero count={operators.length || 0} style={{ backgroundColor: operators.length > 0 ? '#52c41a' : '#7f9474' }} />,
      },
      {
        key: 'resource',
        label: 'Resource',
        children: renderNodes(resources),
        extra: <Badge showZero count={resources.length || 0} style={{ backgroundColor: resources.length > 0 ? '#52c41a' : '#7f9474' }} />,
      },
    ],
    [operators, resources],
  );

  function searchNode(val: string) {
    if (!val) {
      groupNodes(nodes);
    } else {
      const lowerSearchTerm = val.toLowerCase();
      const searchOperators = operators.filter((node) => node.label.toLowerCase().includes(lowerSearchTerm));
      const searchResources = resources.filter((node) => node.label.toLowerCase().includes(lowerSearchTerm));
      setOperators(searchOperators);
      setResources(searchResources);
    }
  }

  function onDragStart(event: DragEvent, node: IFlowNode) {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(node));
    event.dataTransfer.effectAllowed = 'move';
  }

  function renderNodes(nodes: Array<IFlowNode>) {
    if (nodes?.length > 0) {
      return (
        <List
          className="overflow-hidden overflow-y-auto"
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
                avatar={<Avatar src={node.icon || '/icons/node/default_node_icon.svg'} size={'large'} />}
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
  }

  return (
    <Popover
      placement="bottom"
      trigger={['click']}
      content={
        <div className="w-[320px] overflow-hidden overflow-y-auto scrollbar-default">
          <p className="my-4 font-bold">{t('add_node')}</p>
          <Search placeholder="Search node" onSearch={searchNode} />
          <Divider className="my-2" />
          <Collapse className="max-h-[538px]" size="small" defaultActiveKey={['operator']} ghost items={items} />
        </div>
      }
    >
      <Button
        type="primary"
        className="flex items-center justify-center rounded-full left-4 top-4"
        style={{ zIndex: 1050 }}
        icon={<PlusOutlined />}
      ></Button>
    </Popover>
  );
};

export default AddNodes;
