import { CaretRightOutlined, CheckOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { GPTVis } from '@antv/gpt-vis';
import { Collapse } from 'antd';

import markdownComponents, { markdownPlugins, preprocessLaTeX } from './config';

interface Props {
  data: {
    name: string;
    num: number;
    status: 'complete' | 'todo';
    agent: string;
    markdown: string;
  }[];
}

function AgentPlans({ data }: Props) {
  if (!data || !data.length) return null;

  return (
    <Collapse
      bordered
      className='my-3'
      expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
      items={data.map((item, index) => {
        return {
          key: index,
          label: (
            <div>
              <span>
                {item.name} - {item.agent}
              </span>
              {item.status === 'complete' ? (
                <CheckOutlined className='!text-green-500 ml-2' />
              ) : (
                <ClockCircleOutlined className='!text-gray-500 ml-2' />
              )}
            </div>
          ),
          children: (
            <GPTVis components={markdownComponents} {...markdownPlugins}>
              {preprocessLaTeX(item.markdown)}
            </GPTVis>
          ),
        };
      })}
    />
  );
}

export default AgentPlans;
