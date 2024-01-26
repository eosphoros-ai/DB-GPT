import React from 'react';
import DBIcon from '../common/db-icon';
import { Tooltip } from 'antd';

export default function AgentCard() {
  const renderAgentCard = () => {
    return <div></div>;
  };
  return (
    <div className="relative cursor-pointer ml-14 mb-5 flex flex-shrink-0 flex-wrap flex-col p-4 w-72 h-32 rounded justify-between text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1">
      <DBIcon src={'/icons/db2.png'} label="1112" className=" mr-1 inline-block mt-[-4px]"></DBIcon>
      <div className="flex items-center">
        <div className="flex flex-col">
          <h2 className="text-sm font-semibold">大大大</h2>
        </div>
      </div>
      <Tooltip title={'大大大'}>
        <p className="text-sm text-gray-500 font-normal line-clamp-2">大大大</p>
      </Tooltip>
    </div>
  );
}
