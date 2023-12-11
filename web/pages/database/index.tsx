'use client';

import React, { useMemo, useState } from 'react';
import { useAsyncEffect } from 'ahooks';
import { Badge, Button, Card, Drawer, Empty, Modal, Spin, message } from 'antd';
import FormDialog from '@/components/database/form-dialog';
import { apiInterceptors, getDbList, getDbSupportType, postDbDelete } from '@/client/api';
import DBCard from '@/components/database/db-card';
import { DeleteFilled, EditFilled, PlusOutlined } from '@ant-design/icons';
import { DBOption, DBType, DbListResponse, DbSupportTypeResponse } from '@/types/db';
import MuiLoading from '@/components/common/loading';
import { dbMapper } from '@/utils';

type DBItem = DbListResponse[0];

export function isFileDb(dbTypeList: DBOption[], dbType: DBType) {
  return dbTypeList.find((item) => item.value === dbType)?.isFileDb;
}

function Database() {
  const [dbList, setDbList] = useState<DbListResponse>([]);
  const [dbSupportList, setDbSupportList] = useState<DbSupportTypeResponse>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<{ open: boolean; info?: DBItem; dbType?: DBType }>({ open: false });
  const [draw, setDraw] = useState<{ open: boolean; dbList?: DbListResponse; name?: string; type?: DBType }>({ open: false });

  const getDbSupportList = async () => {
    const [_, data] = await apiInterceptors(getDbSupportType());
    setDbSupportList(data ?? []);
  };

  const refreshDbList = async () => {
    setLoading(true);
    const [_, data] = await apiInterceptors(getDbList());
    setDbList(data ?? []);
    setLoading(false);
  };

  const dbTypeList = useMemo(() => {
    const supportDbList = dbSupportList.map((item) => {
      const { db_type, is_file_db } = item;

      return { ...dbMapper[db_type], value: db_type, isFileDb: is_file_db };
    }) as DBOption[];
    const unSupportDbList = Object.keys(dbMapper)
      .filter((item) => !supportDbList.some((db) => db.value === item))
      .map((item) => ({ ...dbMapper[item], value: dbMapper[item].label, disabled: true })) as DBOption[];
    return [...supportDbList, ...unSupportDbList];
  }, [dbSupportList]);

  const onModify = (item: DBItem) => {
    setModal({ open: true, info: item });
  };

  const onDelete = (item: DBItem) => {
    Modal.confirm({
      title: 'Tips',
      content: `Do you Want to delete the ${item.db_name}?`,
      onOk() {
        return new Promise<void>(async (resolve, reject) => {
          try {
            const [err] = await apiInterceptors(postDbDelete(item.db_name));
            if (err) {
              message.error(err.message);
              reject();
              return;
            }
            message.success('success');
            refreshDbList();
            resolve();
          } catch (e: any) {
            reject();
          }
        });
      },
    });
  };

  const dbListByType = useMemo(() => {
    const mapper = dbTypeList.reduce((acc, item) => {
      acc[item.value] = dbList.filter((dbConn) => dbConn.db_type === item.value);
      return acc;
    }, {} as Record<DBType, DbListResponse>);
    return mapper;
  }, [dbList, dbTypeList]);

  useAsyncEffect(async () => {
    await refreshDbList();
    await getDbSupportList();
  }, []);

  const handleDbTypeClick = (info: DBOption) => {
    const dbItems = dbList.filter((item) => item.db_type === info.value);
    setDraw({ open: true, dbList: dbItems, name: info.label, type: info.value });
  };

  return (
    <div className="relative p-4 md:p-6 bg-[#FAFAFA] dark:bg-transparent min-h-full overflow-y-auto">
      <MuiLoading visible={loading} />
      <div className="mb-4">
        <Button
          type="primary"
          className="flex items-center"
          icon={<PlusOutlined />}
          onClick={() => {
            setModal({ open: true });
          }}
        >
          Create
        </Button>
      </div>
      <div className="flex flex-wrap gap-2 md:gap-4">
        {dbTypeList.map((item) => (
          <Badge key={item.value} count={dbListByType[item.value].length}>
            <DBCard
              info={item}
              onClick={() => {
                handleDbTypeClick(item);
              }}
            />
          </Badge>
        ))}
      </div>
      <FormDialog
        open={modal.open}
        dbTypeList={dbTypeList}
        choiceDBType={modal.dbType}
        editValue={modal.info}
        dbNames={dbList.map((item) => item.db_name)}
        onSuccess={() => {
          setModal({ open: false });
          refreshDbList();
        }}
        onClose={() => {
          setModal({ open: false });
        }}
      />
      <Drawer
        title={draw.name}
        placement="right"
        onClose={() => {
          setDraw({ open: false });
        }}
        open={draw.open}
      >
        {draw.type && dbListByType[draw.type] && dbListByType[draw.type].length ? (
          <>
            <Button
              type="primary"
              className="mb-4 flex items-center"
              icon={<PlusOutlined />}
              onClick={() => {
                setModal({ open: true, dbType: draw.type });
              }}
            >
              Create
            </Button>
            {dbListByType[draw.type].map((item) => (
              <Card
                key={item.db_name}
                title={item.db_name}
                extra={
                  <>
                    <EditFilled
                      className="mr-2"
                      style={{ color: '#1b7eff' }}
                      onClick={() => {
                        onModify(item);
                      }}
                    />
                    <DeleteFilled
                      style={{ color: '#ff1b2e' }}
                      onClick={() => {
                        onDelete(item);
                      }}
                    />
                  </>
                }
                className="mb-4"
              >
                {item.db_path ? (
                  <p>path: {item.db_path}</p>
                ) : (
                  <>
                    <p>host: {item.db_host}</p>
                    <p>username: {item.db_user}</p>
                    <p>port: {item.db_port}</p>
                  </>
                )}
                <p>remark: {item.comment}</p>
              </Card>
            ))}
          </>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_DEFAULT}>
            <Button
              type="primary"
              className="flex items-center mx-auto"
              icon={<PlusOutlined />}
              onClick={() => {
                setModal({ open: true, dbType: draw.type });
              }}
            >
              Create Now
            </Button>
          </Empty>
        )}
      </Drawer>
    </div>
  );
}

export default Database;
