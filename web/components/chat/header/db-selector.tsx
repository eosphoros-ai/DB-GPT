import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, postChatModeParamsList } from '@/client/api';
import { IDB } from '@/types/chat';
import { dbMapper } from '@/utils';
import { useAsyncEffect } from 'ahooks';
import { Select } from 'antd';
import { useContext, useEffect, useMemo, useState } from 'react';
import DBIcon from '@/components/common/db-icon';

function DBSelector() {
  const { scene, dbParam, setDbParam } = useContext(ChatContext);

  const [dbs, setDbs] = useState<IDB[]>([]);

  useAsyncEffect(async () => {
    const [, res] = await apiInterceptors(postChatModeParamsList(scene as string));
    setDbs(res ?? []);
  }, [scene]);

  const dbOpts = useMemo(
    () =>
      dbs.map?.((db: IDB) => {
        return { name: db.param, ...dbMapper[db.type] };
      }),
    [dbs],
  );

  useEffect(() => {
    if (dbOpts?.length && !dbParam) {
      setDbParam(dbOpts[0].name);
    }
  }, [dbOpts, setDbParam, dbParam]);

  if (!dbOpts?.length) return null;

  return (
    <Select
      value={dbParam}
      className="w-36"
      onChange={(val) => {
        setDbParam(val);
      }}
    >
      {dbOpts.map((item) => (
        <Select.Option key={item.name}>
          <DBIcon width={24} height={24} src={item.icon} label={item.label} className="w-[1.5em] h-[1.5em] mr-1 inline-block mt-[-4px]" />
          {item.name}
        </Select.Option>
      ))}
    </Select>
  );
}

export default DBSelector;
