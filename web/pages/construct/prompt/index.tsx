import { apiInterceptors, deletePrompt, getPromptList } from '@/client/api';
import useUser from '@/hooks/use-user';
import ConstructLayout from '@/new-components/layout/Construct';
import { IPrompt, PromptListResponse } from '@/types/prompt';
import { PlusOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import type { SegmentedProps } from 'antd';
import { App, Button, Popconfirm, Segmented, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { TFunction } from 'i18next';
import { useRouter } from 'next/router';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import styles from './styles.module.css';

const LangMap = { zh: '中文', en: 'English' };

const DeleteBtn: React.FC<{ record: IPrompt; refresh: () => void }> = ({ record, refresh }) => {
  const userInfo = useUser();
  const { t } = useTranslation();

  const { message } = App.useApp();

  // 删除prompt
  const { run: deletePromptRun, loading: deleteLoading } = useRequest(
    async record => {
      await deletePrompt({
        ...record,
      });
    },
    {
      manual: true,
      onSuccess: async () => {
        message.success('删除成功');
        await refresh();
      },
    },
  );

  if (userInfo?.user_id !== record?.user_id) {
    return null;
  }

  return (
    <Popconfirm title='确认删除吗？' onConfirm={async () => await deletePromptRun(record)}>
      <Button loading={deleteLoading}>{t('Delete')}</Button>
    </Popconfirm>
  );
};

const Prompt = () => {
  const router = useRouter();
  const { t } = useTranslation();
  const [promptType, setPromptType] = useState<string>('common');
  const [promptList, setPromptList] = useState<PromptListResponse>();

  const {
    run: getPrompts,
    loading,
    refresh,
  } = useRequest(
    async (page = 1, page_size = 6) => {
      const [_, data] = await apiInterceptors(
        getPromptList({
          page,
          page_size,
        }),
      );
      return data;
    },
    {
      manual: true,
      onSuccess: data => {
        setPromptList(data!);
      },
    },
  );

  const handleEditBtn = (prompt: IPrompt) => {
    localStorage.setItem('edit_prompt_data', JSON.stringify(prompt));
    router.push('/construct/prompt/edit');
  };

  const handleAddBtn = () => {
    router.push('/construct/prompt/add');
  };

  const getColumns = (t: TFunction, handleEdit: (prompt: IPrompt) => void): ColumnsType<IPrompt> => [
    {
      title: t('Prompt_Info_Name'),
      dataIndex: 'prompt_name',
      key: 'prompt_name',
      width: '10%',
    },
    {
      title: t('Prompt_Info_Scene'),
      dataIndex: 'chat_scene',
      key: 'chat_scene',
      width: '10%',
    },
    {
      title: t('language'),
      dataIndex: 'prompt_language',
      key: 'prompt_language',
      render: lang => (lang ? LangMap[lang as keyof typeof LangMap] : '-'),
      width: '10%',
    },
    {
      title: t('Prompt_Info_Content'),
      dataIndex: 'content',
      key: 'content',
      render: content => <Typography.Paragraph ellipsis={{ rows: 2, tooltip: true }}>{content}</Typography.Paragraph>,
    },
    {
      title: t('Operation'),
      dataIndex: 'operate',
      key: 'operate',
      render: (_, record) => (
        <Space align='center'>
          <Button
            onClick={() => {
              handleEdit(record);
            }}
            type='primary'
          >
            {t('Edit')}
          </Button>
          <DeleteBtn record={record} refresh={refresh} />
        </Space>
      ),
    },
  ];

  useEffect(() => {
    getPrompts();
  }, [promptType]);

  const items: SegmentedProps['options'] = [
    {
      value: 'common',
      label: t('Public') + ' Prompts',
    },
    // {
    //   value: 'private',
    //   label: t('Private') + ' Prompts',
    // },
  ];

  return (
    <ConstructLayout>
      <div className={`px-6 py-2 ${styles['prompt-container']} md:p-6 h-[90vh] overflow-y-auto`}>
        <div className='flex justify-between items-center mb-6'>
          <div className='flex items-center gap-4'>
            <Segmented
              className='backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 border-2 border-white rounded-lg shadow p-1 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
              options={items}
              onChange={type => {
                setPromptType(type as string);
              }}
              value={promptType}
            />
            {/* <Input
              variant="filled"
              prefix={<SearchOutlined />}
              placeholder={t('please_enter_the_keywords')}
              allowClear
              className="w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60"
            /> */}
          </div>
          <div className='flex items-center gap-4 h-10'>
            {/* {promptType === 'common' && (
              <Button className="border-none  h-full" icon={<PlusOutlined />} disabled>
                {t('Add')} Prompts {t('template')}
              </Button>
            )} */}
            <Button
              className='border-none text-white bg-button-gradient h-full'
              onClick={handleAddBtn}
              icon={<PlusOutlined />}
            >
              {t('Add')} Prompts
            </Button>
          </div>
        </div>
        <Table
          columns={getColumns(t, handleEditBtn)}
          dataSource={promptList?.items || []}
          loading={loading}
          rowKey={record => record.prompt_name}
          pagination={{
            pageSize: 6,
            total: promptList?.total_count,
            onChange: async (page, page_size) => {
              await getPrompts(page, page_size);
            },
          }}
        />
      </div>
    </ConstructLayout>
  );
};

export default Prompt;
