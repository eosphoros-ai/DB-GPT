import { ChatContext } from '@/app/chat-context';
import { StarsSvg } from '@/components/icons';
import Icon, { AppstoreFilled } from '@ant-design/icons';
import { Radio } from 'antd';
import { useContext } from 'react';
import './index.css';

export default function ModeTab() {
  const { isContract, setIsContract, scene } = useContext(ChatContext);
  const isShow = scene && ['chat_with_db_execute', 'chat_dashboard'].includes(scene as string);

  if (!isShow) {
    return null;
  }

  return (
    <Radio.Group
      value={isContract}
      defaultValue={true}
      buttonStyle='solid'
      onChange={() => {
        setIsContract(!isContract);
      }}
    >
      <Radio.Button value={false}>
        <Icon component={StarsSvg} className='mr-1' />
        Preview
      </Radio.Button>
      <Radio.Button value={true}>
        <AppstoreFilled className='mr-1' />
        Editor
      </Radio.Button>
    </Radio.Group>
  );
}
