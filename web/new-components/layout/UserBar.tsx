import { UserInfoResponse } from '@/types/userinfo';
import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import { LogoutOutlined } from '@ant-design/icons';
import { Avatar, Dropdown, Space } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import cls from 'classnames';
function UserBar({ onlyAvatar = false }) {
  const { t } = useTranslation();

  const [userInfo, setUserInfo] = useState<UserInfoResponse>();
  useEffect(() => {
    try {
      const user = JSON.parse(localStorage.getItem(STORAGE_USERINFO_KEY) ?? '');
      setUserInfo(user);
    } catch (error) {
      return undefined;
    }
  }, []);

  const logout = () => {
    localStorage.removeItem(STORAGE_USERINFO_KEY);
    window.location.href = `${process.env.LOGOUT_URL}&goto=${encodeURIComponent(window.location.href)}`;
  };

  return (
    <div className="flex flex-1 items-center justify-center">
      <div
        className={cls('flex items-center group w-full', {
          'justify-center': onlyAvatar,
          'justify-between': !onlyAvatar,
        })}
      >
        <span className="flex gap-2 items-center">
          <Avatar src={userInfo?.avatar_url} className="bg-gradient-to-tr from-[#31afff] to-[#1677ff] cursor-pointer">
            {userInfo?.nick_name}
          </Avatar>
          <span
            className={cls('text-sm', {
              hidden: onlyAvatar,
            })}
          >
            {userInfo?.nick_name}
          </span>
        </span>
        {/* <LogoutOutlined
          onClick={logout}
          className={cls('cursor-pointer opacity-0 transition-all hover:opacity-100 group-hover:opacity-70', {
            hidden: onlyAvatar,
          })}
        /> */}
      </div>
    </div>
  );
}

export default UserBar;
