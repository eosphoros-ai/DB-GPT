import { apiInterceptors, delDialogue, getDialogueListPaged } from '@/client/api';
import { IChatDialogueSchema } from '@/types/chat';
import { DeleteOutlined, MessageOutlined, SearchOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Empty, Input, Pagination, Popconfirm, Spin, Tooltip, message } from 'antd';
import debounce from 'lodash/debounce';
import moment from 'moment';
import 'moment/locale/zh-cn';
import { useRouter } from 'next/router';
import { useCallback, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

const PAGE_SIZE = 20;

function ConversationsPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [list, setList] = useState<IChatDialogueSchema[]>([]);
  const [searchKeyword, setSearchKeyword] = useState('');

  const handleSearch = useCallback(
    debounce((value: string) => {
      setSearchKeyword(value);
    }, 300),
    [],
  );

  const filteredList = useMemo(() => {
    if (!searchKeyword.trim()) return list;
    const keyword = searchKeyword.toLowerCase();
    return list.filter(conv => {
      const title = typeof conv.user_input === 'string' ? conv.user_input.toLowerCase() : '';
      return title.includes(keyword);
    });
  }, [list, searchKeyword]);

  const totalRef = useRef<{
    current_page: number;
    total_count: number;
    total_pages: number;
  }>();

  const { loading, run: fetchList } = useRequest(
    async (page = 1) => await apiInterceptors(getDialogueListPaged({ chat_mode: 'chat_react_agent' }, page, PAGE_SIZE)),
    {
      defaultParams: [1],
      onSuccess: data => {
        const [, res] = data;
        setList(res?.items || []);
        totalRef.current = {
          current_page: res?.page || 1,
          total_count: res?.total_count || 0,
          total_pages: res?.total_pages || 0,
        };
      },
    },
  );

  const handleDelete = useCallback(
    async (e: React.MouseEvent, convUid: string) => {
      e.stopPropagation();
      e.preventDefault();
      const [err] = await apiInterceptors(delDialogue(convUid));
      if (!err) {
        message.success('Deleted');
        const current = totalRef.current;
        if (current) {
          const remaining = current.total_count - 1;
          const maxPage = Math.max(1, Math.ceil(remaining / PAGE_SIZE));
          fetchList(Math.min(current.current_page, maxPage));
        }
      }
    },
    [fetchList],
  );

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return '';
    return moment(dateStr).fromNow();
  };

  const getTitle = (conv: IChatDialogueSchema) => {
    if (typeof conv.user_input === 'string' && conv.user_input.trim()) {
      return conv.user_input;
    }
    return t('new_task') || 'New Chat';
  };

  return (
    <div className='flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light'>
      <div className='flex items-center justify-between px-6 py-5 border-b border-gray-100 dark:border-gray-800'>
        <h1 className='text-xl font-semibold text-gray-800 dark:text-gray-100'>{t('all_tasks') || 'All Tasks'}</h1>
        <div className='flex items-center gap-3'>
          <Input
            variant='filled'
            prefix={<SearchOutlined />}
            placeholder='Search conversations...'
            onChange={e => handleSearch(e.target.value)}
            onClear={() => setSearchKeyword('')}
            allowClear
            className='w-[230px] h-[36px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
          />
          <span className='text-sm text-gray-400 whitespace-nowrap'>
            {totalRef.current ? `${totalRef.current.total_count} total` : ''}
          </span>
        </div>
      </div>

      <div className='flex-1 overflow-y-auto px-6 py-4'>
        <Spin spinning={loading}>
          {!loading && list.length === 0 ? (
            <div className='flex items-center justify-center h-64'>
              <Empty description={t('no_tasks') || 'No history yet'} />
            </div>
          ) : !loading && filteredList.length === 0 ? (
            <div className='flex items-center justify-center h-64'>
              <Empty description='No matching conversations' />
            </div>
          ) : (
            <div className='space-y-1'>
              {filteredList.map(conv => (
                <div
                  key={conv.conv_uid}
                  onClick={() => router.push(`/?id=${conv.conv_uid}`)}
                  className='group flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer transition-colors hover:bg-white dark:hover:bg-gray-800 hover:shadow-sm'
                >
                  <div className='flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-gray-100 dark:bg-gray-700'>
                    <MessageOutlined className='text-gray-400 text-sm' />
                  </div>

                  <div className='flex-1 min-w-0'>
                    <div className='text-sm font-medium text-gray-700 dark:text-gray-200 truncate leading-5'>
                      {getTitle(conv)}
                    </div>
                    {conv.gmt_created && (
                      <div className='text-xs text-gray-400 mt-0.5'>{formatTime(conv.gmt_created)}</div>
                    )}
                  </div>

                  <Popconfirm
                    title='Delete this conversation?'
                    onConfirm={e => handleDelete(e as React.MouseEvent, conv.conv_uid)}
                    onCancel={e => {
                      e?.stopPropagation();
                      e?.preventDefault();
                    }}
                    okText='Delete'
                    cancelText='Cancel'
                    okButtonProps={{ danger: true }}
                  >
                    <Tooltip title='Delete'>
                      <div
                        onClick={e => {
                          e.stopPropagation();
                          e.preventDefault();
                        }}
                        className='flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity'
                      >
                        <DeleteOutlined className='text-gray-300 hover:text-red-500 transition-colors' />
                      </div>
                    </Tooltip>
                  </Popconfirm>
                </div>
              ))}
            </div>
          )}
        </Spin>
      </div>

      {(totalRef.current?.total_count ?? 0) > PAGE_SIZE && (
        <div className='flex justify-end px-6 py-4 border-t border-gray-100 dark:border-gray-800'>
          <Pagination
            current={totalRef.current?.current_page}
            total={totalRef.current?.total_count || 0}
            pageSize={PAGE_SIZE}
            showSizeChanger={false}
            showTotal={total => `${total} total`}
            onChange={page => fetchList(page)}
          />
        </div>
      )}
    </div>
  );
}

export default ConversationsPage;
