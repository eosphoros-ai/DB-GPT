import { apiInterceptors, getDbList, getDbSupportType, postDbDelete, postDbRefresh } from '@/client/api';
import GPTCard from '@/components/common/gpt-card';
import MuiLoading from '@/components/common/loading';
import FormDialog from '@/components/database/form-dialog';
import ConstructLayout from '@/new-components/layout/Construct';
import { DBOption, DBType, DbListResponse, DbSupportTypeResponse } from '@/types/db';
import { dbMapper } from '@/utils';
import { DeleteFilled, EditFilled, PlusOutlined, RedoOutlined } from '@ant-design/icons';
import { useAsyncEffect } from 'ahooks';
import { Badge, Button, Card, Drawer, Empty, Modal, Spin, message } from 'antd';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type DBItem = DbListResponse[0];

export function isFileDb(dbTypeList: DBOption[], dbType: DBType) {
  return dbTypeList.find(item => item.value === dbType)?.isFileDb;
}
let getFromRenderData: any = [];
function Database() {
  // const { setCurrentDialogInfo } = useContext(ChatContext);  // unused
  // const router = useRouter(); // unused
  const { t } = useTranslation();

  const [dbList, setDbList] = useState<DbListResponse>([]);
  const [dbSupportList, setDbSupportList] = useState<DbSupportTypeResponse>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<{
    open: boolean;
    info?: string;
    dbType?: DBType;
    dbTypeData?: any[];
    description?: string;
  }>({ open: false });
  const [draw, setDraw] = useState<{
    open: boolean;
    dbList?: DbListResponse;
    name?: string;
    type?: DBType;
  }>({ open: false });
  const [refreshLoading, setRefreshLoading] = useState(false);

  const getDbSupportList = async () => {
    const [, data] = await apiInterceptors(getDbSupportType());
    setDbSupportList(data?.types ?? []);
  };

  const refreshDbList = async () => {
    setLoading(true);
    const [, data] = await apiInterceptors(getDbList());
    setDbList(data ?? []);
    setLoading(false);
  };

  const dbTypeList = useMemo(() => {
    const supportDbList = dbSupportList.map(item => {
      const db_type = item?.name;
      return { ...dbMapper[db_type], value: db_type, isFileDb: true, parameters: item.parameters };
    }) as DBOption[];
    const unSupportDbList = Object.keys(dbMapper)
      .filter(item => !supportDbList.some(db => db.value === item))
      .map(item => ({
        ...dbMapper[item],
        value: dbMapper[item].label,
        disabled: true,
      })) as DBOption[];
    return [...supportDbList, ...unSupportDbList];
  }, [dbSupportList]);

  const onModify = (item: DBItem) => {
    for (let index = 0; index < getFromRenderData.length; index++) {
      const element = getFromRenderData[index];
      if (item.params[element.param_name]) {
        element.default_value = item.params[element.param_name];
      }
    }
    setModal({ open: true, info: item.id, dbType: item.type, description: item.description });
  };

  const onDelete = (item: DBItem) => {
    Modal.confirm({
      title: 'Tips',
      content: `Do you Want to delete the database connection?`,
      onOk() {
        return new Promise<void>((resolve, reject) => {
          handleDelete(item.id, resolve, reject);
        });
      },
    });
  };

  const handleDelete = async (id: string, resolve: () => void, reject: () => void) => {
    try {
      const [err] = await apiInterceptors(postDbDelete(id));
      if (err) {
        message.error(err.message);
        reject();
        return;
      }
      message.success('success');
      refreshDbList();
      resolve();
    } catch {
      reject();
    }
  };

  const dbListByType = useMemo(() => {
    const mapper = dbTypeList.reduce(
      (acc, item) => {
        acc[item.value] = dbList.filter(dbConn => dbConn?.type.toLowerCase() === item.value.toLowerCase());
        return acc;
      },
      {} as Record<DBType, DbListResponse>,
    );
    return mapper;
  }, [dbList, dbTypeList]);

  useAsyncEffect(async () => {
    await refreshDbList();
    await getDbSupportList();
  }, []);

  const handleDbTypeClick = (info: DBOption) => {
    const dbItems = dbList.filter(item => item.type === info.value);
    getFromRenderData = info?.parameters;

    setDraw({
      open: true,
      dbList: dbItems,
      name: info.label,
      type: info.value,
    });
  };

  const onRefresh = async (item: DBItem) => {
    setRefreshLoading(true);
    const [, res] = await apiInterceptors(postDbRefresh({ id: item.id }));
    if (res) message.success(t('refreshSuccess'));
    setRefreshLoading(false);
  };

  const getFileName = (path: string) => {
    if (!path) return '';
    // Handle Windows and Unix style paths
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1];
  };

  return (
    <ConstructLayout>
      <div className='relative min-h-full overflow-y-auto px-6 max-h-[90vh]'>
        <MuiLoading visible={loading} />
        <div className='flex justify-between items-center mb-6'>
          <div className='flex items-center gap-4'></div>

          <div className='flex items-center gap-4'>
            <Button
              className='border-none text-white bg-button-gradient'
              icon={<PlusOutlined />}
              onClick={() => {
                console.log(dbList);
                console.log(dbTypeList);

                setModal({ open: true, dbTypeData: dbTypeList });
              }}
            >
              {t('Add_Datasource')}
            </Button>
          </div>
        </div>

        <div className='flex flex-wrap mx-[-8px] gap-2 md:gap-4'>
          {dbTypeList.map(item => {
            return (
              <Badge key={item.value} count={dbListByType[item.value]?.length} className='min-h-fit'>
                <GPTCard
                  className='h-full'
                  title={item.label}
                  desc={item.desc ?? ''}
                  disabled={item.disabled}
                  icon={item.icon}
                  onClick={() => {
                    if (item.disabled) return;
                    handleDbTypeClick(item);
                  }}
                />
              </Badge>
            );
          })}
        </div>
        <FormDialog
          open={modal.open}
          dbTypeList={dbTypeList}
          getFromRenderData={getFromRenderData}
          description={modal.description}
          choiceDBType={modal.dbType}
          editValue={modal.info}
          dbTypeData={modal.dbTypeData}
          dbNames={dbList.map(item => item.params.database)}
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
          placement='right'
          onClose={() => {
            setDraw({ open: false });
          }}
          open={draw.open}
        >
          {draw.type && dbListByType[draw.type] && dbListByType[draw.type].length ? (
            <Spin spinning={refreshLoading}>
              <Button
                type='primary'
                className='mb-4 flex items-center'
                icon={<PlusOutlined />}
                onClick={() => {
                  setModal({ open: true, dbType: draw.type });
                }}
              >
                Create
              </Button>
              {dbListByType[draw.type].map(item => (
                <Card
                  key={item.params?.database || item.params?.path || ''}
                  title={item.params?.database || getFileName(item.params?.path) || ''}
                  extra={
                    <>
                      <RedoOutlined
                        className='mr-2'
                        style={{ color: 'gray' }}
                        onClick={() => {
                          onRefresh(item);
                        }}
                      />
                      <EditFilled
                        className='mr-2'
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
                  className='mb-4'
                >
                  <>
                    {['host', 'port', 'path', 'user', 'database', 'schema']
                      // Just handle these keys
                      .filter(key => Object.prototype.hasOwnProperty.call(item.params, key))
                      .map(key => (
                        <p key={key}>
                          {key}: {key === 'path' ? getFileName(item.params[key]) : item.params[key]}
                        </p>
                      ))}
                  </>
                  <p>
                    {t('description')}: {item.description}
                  </p>
                </Card>
              ))}
            </Spin>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_DEFAULT}>
              <Button
                type='primary'
                className='flex items-center mx-auto'
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
    </ConstructLayout>
  );
}

export default Database;
