import React, { useCallback } from 'react';
import { Tooltip } from 'antd';
import { DBOption } from '@/types/db';
import DBIcon from '../common/db-icon';

interface Props {
  info: DBOption;
  onClick?: () => void;
}

function DBCard({ info, onClick }: Props) {
  const handleClick = useCallback(() => {
    if (info.disabled) return;
    onClick?.();
  }, [info.disabled, onClick]);

  return (
    <div
      className={`relative flex flex-col py-4 px-4 w-72 h-32 cursor-pointer rounded-lg justify-between text-black bg-white border-gray-200 border hover:shadow-md dark:border-gray-600 dark:bg-black dark:text-white dark:hover:border-white transition-all ${
        info.disabled ? 'grayscale cursor-no-drop' : ''
      }`}
      onClick={handleClick}
    >
      <div className="flex items-center">
        <DBIcon src={info.icon} label={info.label} />
        <div className="flex flex-col">
          <h2 className="text-sm font-semibold">{info.label}</h2>
        </div>
      </div>
      <Tooltip title={info.desc}>
        <p className="text-sm text-gray-500 font-normal line-clamp-2">{info.desc}</p>
      </Tooltip>
    </div>
  );
}

export default DBCard;
