import { ApiOutlined, QrcodeOutlined, ReadOutlined, SmileOutlined } from '@ant-design/icons';
import { FloatButton } from 'antd';
import Image from 'next/image';
import React from 'react';

const FloatHelper: React.FC = () => {
  return (
    <FloatButton.Group trigger="hover" icon={<SmileOutlined />}>
      <FloatButton icon={<QrcodeOutlined />} tooltip={<Image src="/images/QR.png" alt="english" width={300} height={200}></Image>} />
      <FloatButton icon={<ReadOutlined />} href="https://yuque.antfin.com/datafun/nqnxur" target="_blank" tooltip="文档" />
      <FloatButton icon={<ApiOutlined />} href="https://yuque.antfin.com/datafun/nqnxur/blekla63691o3gzg" target="_blank" tooltip="SDK接入" />
    </FloatButton.Group>
  );
};
export default FloatHelper;
