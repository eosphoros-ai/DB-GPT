import { CaretRightOutlined, CheckOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { Collapse } from 'antd';
import { MarkdownVis } from '@antv/gpt-vis';
import markdownComponents from './config';

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
      className="my-3"
      expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
      items={data.map((item, index) => {
        return {
          key: index,
          label: (
            <div className="whitespace-normal">
              <span>
                {item.name} - {item.agent}
              </span>
              {item.status === 'complete' ? (
                <CheckOutlined className="!text-green-500 ml-2" />
              ) : (
                <ClockCircleOutlined className="!text-gray-500 ml-2" />
              )}
            </div>
          ),
          children: <MarkdownVis components={markdownComponents}>{item.markdown}</MarkdownVis>,
        };
      })}
    />
  );
}

export default AgentPlans;
