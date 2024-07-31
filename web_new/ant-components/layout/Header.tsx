import UserBar from '@/ant-components/layout/UserBar';
import { ApiOutlined, ReadOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useRouter } from 'next/router';

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Image from 'next/image';

const Header: React.FC = () => {
  const { t } = useTranslation();
  const router = useRouter();

  const [showHeader, setShowHeader] = useState(true);

  useEffect(() => {
    if (
      router.pathname === '/construct/flow/canvas' ||
      router.pathname === '/construct/app/extra' ||
      (router.pathname === '/chat' && router.asPath !== '/chat')
    ) {
      setShowHeader(false);
    } else {
      setShowHeader(true);
    }
  }, [router]);

  if (!showHeader) {
    return null;
  }

  return (
    <header className="flex items-center justify-end fixed top-0 right-0 h-14 pr-11 bg-transparent">
      <a href="https://yuque.antfin.com/datafun/nqnxur" target="_blank" className="flex items-center h-full mr-4">
        <Tooltip title={t('docs')}>
          <ReadOutlined />
        </Tooltip>
      </a>
      <a href="https://yuque.antfin.com/datafun/nqnxur/blekla63691o3gzg" target="_blank" className="flex items-center h-full">
        <Tooltip title={t('sdk_insert')}>
          <ApiOutlined />
        </Tooltip>
      </a>
      <Tooltip
        className="ml-4"
        title={
          <span>
            <Image src="/images/QR.png" alt="english" width={300} height={200}></Image>
          </span>
        }
      >
        <span className="text-sm">帮助中心</span>
      </Tooltip>
      {/* <UserBar /> */}
    </header>
  );
};

export default Header;
