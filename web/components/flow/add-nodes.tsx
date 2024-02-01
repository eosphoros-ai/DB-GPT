import { apiInterceptors, getFlowNodes } from '@/client/api';
import { IFlowNode } from '@/types/flow';
import { PlusOutlined } from '@ant-design/icons';
import { Badge, Button, Collapse, CollapseProps, Divider, Input, Popover } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FLOW_NODES_KEY } from '@/utils';
import StaticNodes from './static-nodes';

const { Search } = Input;

type GroupType = { category: string; categoryLabel: string; nodes: IFlowNode[] };

const AddNodes: React.FC = () => {
  const { t } = useTranslation();
  const [nodes, setNodes] = useState<Array<IFlowNode>>([]);
  const [groups, setGroups] = useState<Array<GroupType>>([]);
  const [searchValue, setSearchValue] = useState<string>('');

  useEffect(() => {
    getNodes();
  }, []);

  async function getNodes() {
    const [_, data] = await apiInterceptors(getFlowNodes());
    if (data && data.length > 0) {
      setNodes(data);
      setGroups(groupNodes(data));
      localStorage.setItem(FLOW_NODES_KEY, JSON.stringify(data));
    }
  }

  function groupNodes(data: IFlowNode[]) {
    // show operator nodes first, then show resource nodes
    const groups: GroupType[] = [];
    const categoryMap: Record<string, { category: string; categoryLabel: string; nodes: IFlowNode[] }> = {};
    data.forEach((item) => {
      const { category, category_label } = item;
      if (!categoryMap[category]) {
        categoryMap[category] = { category, categoryLabel: category_label, nodes: [] };
        if (category === 'operator') {
          groups.unshift(categoryMap[category]);
        } else {
          groups.push(categoryMap[category]);
        }
      }
      categoryMap[category].nodes.push(item);
    });
    return groups;
  }

  const items: CollapseProps['items'] = useMemo(() => {
    if (!searchValue) {
      return groups.map(({ category, categoryLabel, nodes }) => ({
        key: category,
        label: categoryLabel,
        children: <StaticNodes nodes={nodes} />,
        extra: <Badge showZero count={nodes.length || 0} style={{ backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474' }} />,
      }));
    } else {
      const searchedNodes = nodes.filter((node) => node.label.toLowerCase().includes(searchValue.toLowerCase()));
      return groupNodes(searchedNodes).map(({ category, categoryLabel, nodes }) => ({
        key: category,
        label: categoryLabel,
        children: <StaticNodes nodes={nodes} />,
        extra: <Badge showZero count={nodes.length || 0} style={{ backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474' }} />,
      }));
    }
  }, [groups, searchValue]);

  function searchNode(val: string) {
    setSearchValue(val);
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
