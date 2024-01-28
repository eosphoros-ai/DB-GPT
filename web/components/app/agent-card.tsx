import React from 'react';
import DBIcon from '../common/db-icon';
import { Tooltip } from 'antd';

export default function AgentCard() {
  return (
    <div className="relative cursor-pointer mr-8 mb-5 flex flex-shrink-0 flex-wrap flex-col p-4 w-72 h-32 rounded  text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1">
      <div className="flex items-center mb-5">
        <DBIcon src={'/icons/db2.png'} label="title" className=" mr-1 inline-block mt-[-4px]"></DBIcon>
        <h2 className="text-sm font-semibold">Title</h2>
      </div>
      <Tooltip title={'大大大'}>
        <p className="text-sm text-gray-500 font-normal line-clamp-2">Description</p>
      </Tooltip>
    </div>
  );
}
