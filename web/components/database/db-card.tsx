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
      className={`relative flex flex-col p-4 w-72 h-32 rounded justify-between text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1 ${
        info.disabled ? 'grayscale cursor-no-drop' : 'cursor-pointer'
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
