import { ReadOutlined, SmileOutlined } from '@ant-design/icons';
import { FloatButton } from 'antd';
import React from 'react';

const FloatHelper: React.FC = () => {
  return (
    <div className='fixed right-4 md:right-6 bottom-[240px] md:bottom-[220px] z-[997]'>
      <FloatButton.Group trigger='hover' icon={<SmileOutlined />}>
        <FloatButton icon={<ReadOutlined />} href='http://docs.dbgpt.cn' target='_blank' tooltip='Documents' />
      </FloatButton.Group>
    </div>
  );
};

export default FloatHelper;
