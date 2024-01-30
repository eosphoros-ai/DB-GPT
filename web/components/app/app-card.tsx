import React, { useEffect, useState } from 'react';
import DBIcon from '../common/db-icon';
import CollectIcon from '../icons/collect';
import CollectedIcon from '../icons/collected';
import { Button } from 'antd';
import { apiInterceptors, collectApp, getAppList } from '@/client/api';
import { IApp } from '@/types/app';

interface IProps {
  updateApps: () => void;
  app: IApp;
}

export default function AppCard(props: IProps) {
  const { updateApps, app } = props;
  const [isCollect, setIsCollect] = useState(false);

  const collect = async () => {
    const [error, data] = await apiInterceptors(collectApp({ app_code: app.app_code }));
    if (error) return;
    updateApps();
    setIsCollect(true);
  };

  return (
    <div className="relative cursor-pointer mr-8 mb-5 h-72 flex flex-shrink-0 flex-col p-4 w-72 lg:w-72 rounded  text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1 ">
      <div className="flex justify-between">
        <div className="flex items-center">
          <DBIcon src={'/icons/db2.png'} label="1112" className=" mr-1 inline-block mt-[-4px]"></DBIcon>
          <h2 className="text-sm font-semibold">{app?.app_name}</h2>
        </div>
        <div onClick={collect}>{!isCollect ? <CollectIcon /> : <CollectedIcon />}</div>
      </div>
      <div className="text-sm mt-2 p-6 pt-2 ">
        <p className="font-semibold">简介:</p>
        <p className=" truncate mb-2">{app?.app_describe}</p>
        {app?.language && (
          <>
            <p className="font-semibold">语言:</p>
            <p className=" truncate mb-2">{app?.language}</p>
          </>
        )}
        <p className="font-semibold">组织模式:</p>
        <p className=" truncate">{app?.team_mode}</p>
      </div>
      <div className="w-full flex justify-center">
        <Button danger>delete</Button>
      </div>
    </div>
  );
}
