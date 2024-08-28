import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getFlowNodes } from '@/client/api';
import { CaretLeftOutlined, CaretRightOutlined } from '@ant-design/icons';
import type { CollapseProps } from 'antd';
import { Badge, Collapse, Input, Layout, Space } from 'antd';
import React, { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import StaticNodes from './static-nodes';
import { IFlowNode } from '@/types/flow';
import { FLOW_NODES_KEY } from '@/utils';

const { Search } = Input;
const { Sider } = Layout;

type GroupType = {
  category: string;
  categoryLabel: string;
  nodes: IFlowNode[];
};

const zeroWidthTriggerDefaultStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 16,
  height: 48,
  position: 'absolute',
  top: '50%',
  transform: 'translateY(-50%)',
  border: '1px solid #d6d8da',
  borderRadius: 8,
  right: -8,
};

const AddNodesSider: React.FC = () => {
  const { t } = useTranslation();
  const { mode } = useContext(ChatContext);
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [searchValue, setSearchValue] = useState<string>('');
  const [operators, setOperators] = useState<Array<IFlowNode>>([]);
  const [resources, setResources] = useState<Array<IFlowNode>>([]);
  const [operatorsGroup, setOperatorsGroup] = useState<GroupType[]>([]);
  const [resourcesGroup, setResourcesGroup] = useState<GroupType[]>([]);

  useEffect(() => {
    getNodes();
  }, []);

  async function getNodes() {
    const [_, data] = await apiInterceptors(getFlowNodes());
    if (data && data.length > 0) {
      localStorage.setItem(FLOW_NODES_KEY, JSON.stringify(data));
      const operatorNodes = data.filter(
        (node) => node.flow_type === 'operator'
      );
      const resourceNodes = data.filter(
        (node) => node.flow_type === 'resource'
      );
      setOperators(operatorNodes);
      setResources(resourceNodes);
      setOperatorsGroup(groupNodes(operatorNodes));
      setResourcesGroup(groupNodes(resourceNodes));
    }
  }

  const triggerStyle: React.CSSProperties = useMemo(() => {
    if (collapsed) {
      return {
        ...zeroWidthTriggerDefaultStyle,
        right: -16,
        borderRadius: '0px 8px 8px 0',
        borderLeft: '1px solid #d5e5f6',
      };
    }
    return {
      ...zeroWidthTriggerDefaultStyle,
      borderLeft: '1px solid #d6d8da',
    };
  }, [collapsed]);

  function groupNodes(data: IFlowNode[]) {
    const groups: GroupType[] = [];
    const categoryMap: Record<
      string,
      { category: string; categoryLabel: string; nodes: IFlowNode[] }
    > = {};
    data.forEach((item) => {
      const { category, category_label } = item;
      if (!categoryMap[category]) {
        categoryMap[category] = {
          category,
          categoryLabel: category_label,
          nodes: [],
        };
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
        extra: (
          <Badge
            showZero
            count={nodes.length || 0}
            style={{
              backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474',
            }}
          />
        ),
      }));
    } else {
      const searchedNodes = operators.filter((node) =>
        node.label.toLowerCase().includes(searchValue.toLowerCase())
      );
      return groupNodes(searchedNodes).map(
        ({ category, categoryLabel, nodes }) => ({
          key: category,
          label: categoryLabel,
          children: <StaticNodes nodes={nodes} />,
          extra: (
            <Badge
              showZero
              count={nodes.length || 0}
              style={{
                backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474',
              }}
            />
          ),
        })
      );
    }
  }, [operatorsGroup, searchValue]);

  const resourceItems: CollapseProps['items'] = useMemo(() => {
    if (!searchValue) {
      return resourcesGroup.map(({ category, categoryLabel, nodes }) => ({
        key: category,
        label: categoryLabel,
        children: <StaticNodes nodes={nodes} />,
        extra: (
          <Badge
            showZero
            count={nodes.length || 0}
            style={{
              backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474',
            }}
          />
        ),
      }));
    } else {
      const searchedNodes = resources.filter((node) =>
        node.label.toLowerCase().includes(searchValue.toLowerCase())
      );
      return groupNodes(searchedNodes).map(
        ({ category, categoryLabel, nodes }) => ({
          key: category,
          label: categoryLabel,
          children: <StaticNodes nodes={nodes} />,
          extra: (
            <Badge
              showZero
              count={nodes.length || 0}
              style={{
                backgroundColor: nodes.length > 0 ? '#52c41a' : '#7f9474',
              }}
            />
          ),
        })
      );
    }
  }, [resourcesGroup, searchValue]);

  function searchNode(val: string) {
    setSearchValue(val);
  }

  return (
    <Sider
      className='flex justify-center items-start nodrag bg-[#ffffff80] border-r border-[#d5e5f6] dark:bg-[#ffffff29] dark:border-[#ffffff66]'
      theme={mode}
      width={280}
      collapsible={true}
      collapsed={collapsed}
      collapsedWidth={0}
      trigger={
        collapsed ? (
          <CaretRightOutlined className='text-base' />
        ) : (
          <CaretLeftOutlined className='text-base' />
        )
      }
      zeroWidthTriggerStyle={triggerStyle}
      onCollapse={(collapsed) => setCollapsed(collapsed)}
    >
      <Space
        direction='vertical'
        className='w-[280px] pt-4 px-4 overflow-hidden overflow-y-auto scrollbar-default'
      >
        <p className='w-full text-base font-semibold text-[#1c2533] dark:text-[rgba(255,255,255,0.85)] line-clamp-1'>
          {t('add_node')}
        </p>

        <Search placeholder='Search node' onSearch={searchNode} allowClear />

        <h2 className='font-semibold'>{t('operators')}</h2>
        <Collapse
          size='small'
          bordered={false}
          className='max-h-[calc((100vh-156px)/2)] overflow-hidden overflow-y-auto scrollbar-default'
          defaultActiveKey={['']}
          items={operatorItems}
        />

        <h2 className='font-semibold'>{t('resource')}</h2>
        <Collapse
          size='small'
          bordered={false}
          className='max-h-[calc((100vh-156px)/2)] overflow-hidden overflow-y-auto scrollbar-default'
          defaultActiveKey={['']}
          items={resourceItems}
        />
      </Space>
    </Sider>
  );
};

export default AddNodesSider;
