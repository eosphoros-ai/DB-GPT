import { STORAGE_LANG_KEY, STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import { GlobalOutlined } from '@ant-design/icons';
import { Avatar, Popover } from 'antd';
import { useRouter } from 'next/router';
import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface StoredUserInfo {
  user_name: string;
  nick_name: string;
  role: 'super_admin' | 'normal';
  user_group_name: string | null;
  phone?: string;
  email?: string;
  avatar_url?: string;
}

const Header: React.FC = () => {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [showHeader, setShowHeader] = useState(true);
  const [userInfo, setUserInfo] = useState<StoredUserInfo | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_USERINFO_KEY);
      if (raw) {
        setUserInfo(JSON.parse(raw));
      }
    } catch {
      /* empty */
    }
  }, []);

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

  const handleChangeLang = useCallback(() => {
    const language = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(language);
    localStorage.setItem(STORAGE_LANG_KEY, language);
  }, [i18n]);

  if (!showHeader) {
    return null;
  }

  const displayName = userInfo?.nick_name || userInfo?.user_name || 'U';

  const userPopoverContent = (
    <div className='w-56 py-1'>
      <div className='px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider'>{t('user_info')}</div>
      <div className='px-3 py-2 text-sm text-gray-700 dark:text-gray-300'>
        <div className='flex justify-between py-1'>
          <span className='text-gray-400'>{t('user_name')}</span>
          <span>{userInfo?.user_name || '-'}</span>
        </div>
        <div className='flex justify-between py-1'>
          <span className='text-gray-400'>{t('user_group')}</span>
          <span>{userInfo?.user_group_name || '-'}</span>
        </div>
        <div className='flex justify-between py-1'>
          <span className='text-gray-400'>{t('user_role')}</span>
          <span>{userInfo?.role === 'super_admin' ? t('user_super_admin') : t('user_normal')}</span>
        </div>
        {userInfo?.phone && (
          <div className='flex justify-between py-1'>
            <span className='text-gray-400'>{t('user_phone')}</span>
            <span>{userInfo.phone}</span>
          </div>
        )}
        {userInfo?.email && (
          <div className='flex justify-between py-1'>
            <span className='text-gray-400'>{t('user_email')}</span>
            <span>{userInfo.email}</span>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <header className='flex items-center justify-end h-14 pr-6 bg-transparent'>
      <Popover content={t('language')}>
        <div className='flex items-center justify-center cursor-pointer text-lg mr-4' onClick={handleChangeLang}>
          <GlobalOutlined />
        </div>
      </Popover>

      <Popover content={userPopoverContent} trigger='click' placement='bottomRight' arrow={false} overlayInnerStyle={{ padding: 0, borderRadius: 12, overflow: 'hidden' }}>
        <Avatar
          src={userInfo?.avatar_url}
          size={32}
          className='bg-gradient-to-tr from-[#31afff] to-[#1677ff] cursor-pointer flex-shrink-0'
        >
          {displayName}
        </Avatar>
      </Popover>
    </header>
  );
};

export default Header;
