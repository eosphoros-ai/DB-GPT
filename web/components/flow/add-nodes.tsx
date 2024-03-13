import { apiInterceptors, getFlowNodes } from '@/client/api';
import { IFlowNode } from '@/types/flow';
import { PlusOutlined } from '@ant-design/icons';
import { Badge, Button, Collapse, CollapseProps, Input, Popover } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FLOW_NODES_KEY } from '@/utils';
import StaticNodes from './static-nodes';

const { Search } = Input;

type GroupType = { category: string; categoryLabel: string; nodes: IFlowNode[] };

const AddNodes: React.FC = () => {
  const { t } = useTranslation();
  const [operators, setOperators] = useState<Array<IFlowNode>>([]);
  const [resources, setResources] = useState<Array<IFlowNode>>([]);
  const [operatorsGroup, setOperatorsGroup] = useState<GroupType[]>([]);
  const [resourcesGroup, setResourcesGroup] = useState<GroupType[]>([]);
  const [searchValue, setSearchValue] = useState<string>('');

  useEffect(() => {
    getNodes();
  }, []);

  async function getNodes() {
    const [_, data] = await apiInterceptors(getFlowNodes());
    if (data && data.length > 0) {
      localStorage.setItem(FLOW_NODES_KEY, JSON.stringify(data));
      const operatorNodes = data.filter((node) => node.flow_type === 'operator');
      const resourceNodes = data.filter((node) => node.flow_type === 'resource');
      setOperators(operatorNodes);
      setResources(resourceNodes);
      setOperatorsGroup(groupNodes(operatorNodes));
      setResourcesGroup(groupNodes(resourceNodes));
    }
  }

  function groupNodes(data: IFlowNode[]) {
    const groups: GroupType[] = [];
    const categoryMap: Record<string, { category: string; categoryLabel: string; nodes: IFlowNode[] }> = {};
    data.forEach((item) => {
      const { category, category_label } = item;
      if (!categoryMap[category]) {
        categoryMap[category] = { category, categoryLabel: category_label, nodes: [] };
        groups.push(categoryMap[category]);
      }
      categoryMap[category].nodes.push(item);
    });
    return groups;
  }

  const operatorItems: CollapseProps['items'] = useMemo(() => {
    if (!searchValue) {
      return operatorsGroup.map(({ category, categoryLabel, nodes }) => ({
        key: category,
        label: categoryLabel,
        children: <StaticNodes nodes={nodes} />,
        extra: <Badge showZero count={nodes.length || 0} style={{ backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474' }} />,
      }));
    } else {
      const searchedNodes = operators.filter((node) => node.label.toLowerCase().includes(searchValue.toLowerCase()));
      return groupNodes(searchedNodes).map(({ category, categoryLabel, nodes }) => ({
        key: category,
        label: categoryLabel,
        children: <StaticNodes nodes={nodes} />,
        extra: <Badge showZero count={nodes.length || 0} style={{ backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474' }} />,
      }));
    }
  }, [operatorsGroup, searchValue]);

  const resourceItems: CollapseProps['items'] = useMemo(() => {
    if (!searchValue) {
      return resourcesGroup.map(({ category, categoryLabel, nodes }) => ({
        key: category,
        label: categoryLabel,
        children: <StaticNodes nodes={nodes} />,
        extra: <Badge showZero count={nodes.length || 0} style={{ backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474' }} />,
      }));
    } else {
      const searchedNodes = resources.filter((node) => node.label.toLowerCase().includes(searchValue.toLowerCase()));
      return groupNodes(searchedNodes).map(({ category, categoryLabel, nodes }) => ({
        key: category,
        label: categoryLabel,
        children: <StaticNodes nodes={nodes} />,
        extra: <Badge showZero count={nodes.length || 0} style={{ backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474' }} />,
      }));
    }
  }, [resourcesGroup, searchValue]);

  function searchNode(val: string) {
    setSearchValue(val);
  }

  return (
    <Popover
      placement="bottom"
      trigger={['click']}
      content={
        <div className="w-[320px] overflow-hidden overflow-y-auto scrollbar-default">
          <p className="my-2 font-bold">{t('add_node')}</p>
          <Search placeholder="Search node" onSearch={searchNode} />
          <h2 className="my-2 ml-2 font-semibold">{t('operators')}</h2>
          <Collapse
            className="max-h-[300px] overflow-hidden overflow-y-auto scrollbar-default"
            size="small"
            defaultActiveKey={['']}
            items={operatorItems}
          />
          <h2 className="my-2 ml-2 font-semibold">{t('resource')}</h2>
          <Collapse
            className="max-h-[300px] overflow-hidden overflow-y-auto scrollbar-default"
            size="small"
            defaultActiveKey={['']}
            items={resourceItems}
          />
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
