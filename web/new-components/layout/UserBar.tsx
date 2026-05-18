import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import { Avatar } from 'antd';
import cls from 'classnames';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface StoredUserInfo {
  user_id: string;
  user_no: string;
  user_name: string;
  nick_name: string;
  real_name?: string;
  role: 'super_admin' | 'normal';
  user_group_id: number | null;
  user_group_name: string | null;
  phone?: string;
  email?: string;
}

function UserBar({ onlyAvatar = false }) {
  const { t } = useTranslation();
  const [userInfo, setUserInfo] = useState<StoredUserInfo>();
  useEffect(() => {
    try {
      const user = JSON.parse(localStorage.getItem(STORAGE_USERINFO_KEY) ?? '');
      setUserInfo(user);
    } catch {
      return undefined;
    }
  }, []);

  const roleLabel = userInfo?.role === 'super_admin' ? t('user_super_admin') : t('user_normal');

  return (
    <div className='flex flex-1 items-center justify-center'>
      <div
        className={cls('flex items-center group w-full', {
          'justify-center': onlyAvatar,
          'justify-between': !onlyAvatar,
        })}
      >
        <span className='flex gap-2 items-center whitespace-nowrap'>
          <Avatar src={userInfo?.avatar_url} className='bg-gradient-to-tr from-[#31afff] to-[#1677ff] cursor-pointer'>
            {userInfo?.nick_name}
          </Avatar>
          <span
            className={cls('text-sm', {
              hidden: onlyAvatar,
            })}
          >
            {roleLabel}
          </span>
        </span>
      </div>
    </div>
  );
}

export default UserBar;
