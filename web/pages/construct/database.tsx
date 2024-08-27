import BlurredCard, { ChatButton, InnerDropdown } from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getDbList, getDbSupportType, newDialogue, postDbDelete } from '@/client/api';
import MuiLoading from '@/components/common/loading';
import FormDialog from '@/components/database/form-dialog';
import { DBOption, DBType, DbListResponse, DbSupportTypeResponse, IChatDbSchema } from '@/types/db';
import { dbMapper } from '@/utils';
import { DeleteFilled, EditFilled, PlusOutlined } from '@ant-design/icons';
import { useAsyncEffect } from 'ahooks';
import { Button, Card, Drawer, Empty, Modal, Tag, message } from 'antd';
import { useRouter } from 'next/router';
import { useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type DBItem = DbListResponse[0];

export function isFileDb(dbTypeList: DBOption[], dbType: DBType) {
  return dbTypeList.find((item) => item.value === dbType)?.isFileDb;
}

function Database() {
  const { setCurrentDialogInfo } = useContext(ChatContext);
  const { t } = useTranslation();
  const router = useRouter();

  const [dbList, setDbList] = useState<DbListResponse>([]);
  const [dbSupportList, setDbSupportList] = useState<DbSupportTypeResponse>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<{ open: boolean; info?: DBItem; dbType?: DBType }>({ open: false });
  const [draw, setDraw] = useState<{ open: boolean; dbList?: DbListResponse; name?: string; type?: DBType }>({ open: false });

  const getDbSupportList = async () => {
    const [, data] = await apiInterceptors(getDbSupportType());
    setDbSupportList(data ?? []);
  };

  const refreshDbList = async () => {
    setLoading(true);
    const [, data] = await apiInterceptors(getDbList());
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

  const handleChat = async (item: IChatDbSchema) => {
    const [_, data] = await apiInterceptors(
      newDialogue({
        chat_mode: 'chat_with_db_execute',
      }),
    );
    // 知识库对话都默认私有知识库应用下
    if (data?.conv_uid) {
      setCurrentDialogInfo?.({
        chat_scene: data.chat_mode,
        app_code: data.chat_mode,
      });
      localStorage.setItem(
        'cur_dialog_info',
        JSON.stringify({
          chat_scene: data.chat_mode,
          app_code: data.chat_mode,
        }),
      );
      router.push(`/chat?scene=chat_with_db_execute&id=${data?.conv_uid}&db_name=${item.db_name}`);
    }
  };
  return (
    <ConstructLayout>
      <div className="relative min-h-full overflow-y-auto px-6 max-h-[90vh]">
        <MuiLoading visible={loading} />
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            {/* <Input
              variant="filled"
              prefix={<SearchOutlined />}
              placeholder={t('please_enter_the_keywords')}
              // onChange={onSearch}
              // onPressEnter={onSearch}
              allowClear
              className="w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60"
            /> */}
          </div>

          <div className="flex items-center gap-4">
            <Button
              className="border-none text-white bg-button-gradient"
              icon={<PlusOutlined />}
              onClick={() => {
                setModal({ open: true });
              }}
            >
              {t('Add_Datasource')}
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap mx-[-8px]">
          {dbList.map((item) => {
            let targetDBType = dbTypeList.find((i) => i?.value?.toLowerCase() === item.db_type);
            return (
              <BlurredCard
                description={item.db_path ?? ''}
                name={item.db_name}
                key={item.db_name}
                logo={targetDBType?.icon}
                RightTop={
                  <InnerDropdown
                    menu={{
                      items: [
                        {
                          key: 'del',
                          label: (
                            <span
                              className="text-red-400"
                              onClick={() => {
                                onDelete(item);
                              }}
                            >
                              删除
                            </span>
                          ),
                        },
                      ],
                    }}
                  />
                }
                rightTopHover={false}
                Tags={
                  <div>
                    <Tag>{item.db_type}</Tag>
                  </div>
                }
                RightBottom={
                  <ChatButton
                    text={t('start_chat')}
                    onClick={() => {
                      handleChat(item);
                    }}
                  />
                }
                onClick={() => {
                  // if (targetDBType?.disabled) return;
                  // handleDbTypeClick(targetDBType);
                  onModify(item);
                }}
              />
            );
          })}
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
    </ConstructLayout>
  );
}

export default Database;
