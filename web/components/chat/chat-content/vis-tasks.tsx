import { ee, EVENTS } from '@/utils/event-emitter';
import { CheckOutlined, ClockCircleOutlined, CloseOutlined, LoadingOutlined, PauseOutlined } from '@ant-design/icons';

export type VisTasksData = {
  name: string;
  content: string;
  num: number;
  status: string;
  task_id: string;
  model: string;
  agent: string;
  avatar: string;
  tasks: string[];
};

/**
 * VisTasks component that displays a list of tasks.
 * It contains no GPT-Vis components.
 */
export function VisTasks({ data }: { data: VisTasksData[] }) {
  if (!data || !data.length) return null;

  function getStatusIcon(status: string) {
    switch (status) {
      case 'todo':
        return <PauseOutlined className='!text-gray-500 ml-2' />;
      case 'running':
        return <LoadingOutlined className='!text-blue-500 ml-2' />;
      case 'waiting':
        return <ClockCircleOutlined className='!text-yellow-500 ml-2' />;
      case 'retrying':
        return <LoadingOutlined className='!text-orange-500 ml-2' />;
      case 'failed':
        return <CloseOutlined className='!text-red-500 ml-2' />;
      case 'complete':
        return <CheckOutlined className='!text-green-500 ml-2' />;
      default:
        return <ClockCircleOutlined className='!text-gray-500 ml-2' />;
    }
  }

  function onTaskClick(taskId: string) {
    return () => {
      // You can add any additional logic here, such as navigating to a task detail page
      ee.emit(EVENTS.TASK_CLICK, { taskId });
    };
  }

  return (
    <div className='flex flex-col'>
      {data.map(item => {
        return (
          <div
            key={`task-${item.task_id}`}
            className='flex flex-row mb-4 cursor-pointer hover:bg-gray-100 p-2 rounded-lg'
            onClick={onTaskClick(item.task_id)}
          >
            <img src={`/agents/${item.avatar}`} className='flex-0 rounded-2xl w-8 h-8 inline-block mr-2' />
            <div className='flex flex-col flex-1'>
              <div className='flex-row mb-1'>
                <span className='text-xs break-all'>
                  {item.name} <span className='text-blue-500 font-medium'>@{item.agent}</span>
                </span>
                {getStatusIcon(item.status)}
              </div>
              <div className='text-xs break-all text-gray-500'>{item.content}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
