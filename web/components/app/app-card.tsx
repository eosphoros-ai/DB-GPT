import React, { useEffect, useState } from 'react';
import DBIcon from '../common/db-icon';
import CollectIcon from '../icons/collect';
import CollectedIcon from '../icons/collected';
import { Button } from 'antd';
import { apiInterceptors, collectApp, getAppList } from '@/client/api';
import { IApp } from '@/types/app';

export default function AppCard() {
  const [isCollect, setIsCollect] = useState(false);
  const [appList, setAppList] = useState<IApp[]>([]);

  const initData = async () => {
    const [_, data] = await apiInterceptors(getAppList());
    setAppList(appList);
  };

  const collect = async (app_code: string) => {
    const [error, data] = await apiInterceptors(collectApp({ app_code }));
    if (error) return;
    initData();
  };

  return (
    <div className="relative cursor-pointer mr-8 mb-5 flex flex-shrink-0 flex-col p-4 w-72 lg:w-72 rounded  text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1 ">
      <div className="flex justify-between">
        <div className="flex items-center">
          <DBIcon src={'/icons/db2.png'} label="1112" className=" mr-1 inline-block mt-[-4px]"></DBIcon>
          <h2 className="text-sm font-semibold">Title</h2>
        </div>
        <div
          onClick={() => {
            collect("213");
          }}
        >
          {!isCollect ? <CollectIcon /> : <CollectedIcon />}
        </div>
      </div>
      <div className="text-sm mt-2 p-6 pt-2 ">
        <p className="font-semibold">应用:</p>
        <p className=" truncate mt-2">应用</p>
        <p className="font-semibold">简介:</p>
        <p className=" truncate mt-2">简介</p>
        <p className="font-semibold">语言:</p>
        <p className=" truncate mt-2">语言</p>
        <p className="font-semibold">组织模式:</p>
        <p className=" truncate">组织模式</p>
      </div>
      <div className="w-full flex justify-center">
        <Button danger>delete</Button>
      </div>
    </div>
  );
}
