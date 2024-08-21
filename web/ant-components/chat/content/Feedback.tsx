import { apiInterceptors, feedbackAdd, getFeedbackReasons, cancelFeedback } from '@/client/api';
import { CopyOutlined, DislikeOutlined, LikeOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Divider, Input, Popover, Tag, message } from 'antd';
import classNames from 'classnames';
import copy from 'copy-to-clipboard';
import { useSearchParams } from 'next/navigation';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface Tags {
  reason: string;
  reason_type: string;
}

const DislikeContent: React.FC<{
  list: Tags[];
  loading: boolean;
  feedback: (params: { feedback_type: string; reason_types?: string[] | undefined; remark?: string | undefined }) => void;
  setFeedbackOpen: React.Dispatch<React.SetStateAction<boolean>>;
}> = ({ list, loading, feedback, setFeedbackOpen }) => {
  const { t } = useTranslation();
  const [selectedTags, setSelectedTags] = useState<Tags[]>([]);
  const [remark, setRemark] = useState('');

  return (
    <div className="flex flex-col">
      <div className="flex flex-1 flex-wrap w-72">
        {list?.map((item) => {
          const isSelect = selectedTags.findIndex((tag) => tag.reason_type === item.reason_type) > -1;
          return (
            <Tag
              key={item.reason_type}
              className={`text-xs text-[#525964] mb-2 p-1 px-2 rounded-md cursor-pointer ${isSelect ? 'border-[#0c75fc] text-[#0c75fc]' : ''}`}
              onClick={() => {
                setSelectedTags((preArr: Tags[]) => {
                  const index = preArr.findIndex((tag) => tag.reason_type === item.reason_type);
                  if (index > -1) {
                    return [...preArr.slice(0, index), ...preArr.slice(index + 1)];
                  }
                  return [...preArr, item];
                });
              }}
            >
              {item.reason}
            </Tag>
          );
        })}
      </div>
      <Input.TextArea
        placeholder={t('feedback_tip')}
        className="w-64 h-20 resize-none mb-2"
        value={remark}
        onChange={(e) => setRemark(e.target.value.trim())}
      />
      <div className="flex gap-2 justify-end">
        <Button
          className="w-16 h-8"
          onClick={() => {
            setFeedbackOpen(false);
          }}
        >
          取消
        </Button>
        <Button
          type="primary"
          className="min-w-16 h-8"
          onClick={async () => {
            const reason_types = selectedTags.map((item) => item.reason_type);
            await feedback?.({
              feedback_type: 'unlike',
              reason_types,
              remark,
            });
          }}
          loading={loading}
        >
          确认
        </Button>
      </div>
    </div>
  );
};

const Feedback: React.FC<{ content: Record<string, any> }> = ({ content }) => {
  const { t } = useTranslation();

  const searchParams = useSearchParams();
  const chatId = searchParams?.get('id') ?? '';

  const [messageApi, contextHolder] = message.useMessage();
  const [feedbackOpen, setFeedbackOpen] = useState<boolean>(false);
  const [status, setStatus] = useState<'like' | 'unlike' | 'none'>(content?.feedback?.feedback_type);
  const [list, setList] = useState<Tags[]>();

  // 复制回答
  const onCopyContext = async (context: any) => {
    const pureStr = context?.replace(/\trelations:.*/g, '');
    const result = copy(pureStr);
    if (result) {
      if (pureStr) {
        messageApi.open({ type: 'success', content: t('copy_success') });
      } else {
        messageApi.open({ type: 'warning', content: t('copy_nothing') });
      }
    } else {
      messageApi.open({ type: 'error', content: t('copy_failed') });
    }
  };

  // 点赞/踩
  const { run: feedback, loading } = useRequest(
    async (params: { feedback_type: string; reason_types?: string[]; remark?: string }) =>
      await apiInterceptors(
        feedbackAdd({
          conv_uid: chatId,
          message_id: content.order + '',
          feedback_type: params.feedback_type,
          reason_types: params.reason_types,
          remark: params.remark,
        }),
      ),
    {
      manual: true,
      onSuccess: (data) => {
        const [, res] = data;
        setStatus(res?.feedback_type);
        message.success('反馈成功');
        setFeedbackOpen(false);
      },
    },
  );

  // 反馈原因类型
  const { run: getReasonList } = useRequest(async () => await apiInterceptors(getFeedbackReasons()), {
    manual: true,
    onSuccess: (data) => {
      const [, res] = data;
      setList(res || []);
      if (res) {
        setFeedbackOpen(true);
      }
    },
  });

  // 取消反馈
  const { run: cancel } = useRequest(async () => await apiInterceptors(cancelFeedback({ conv_uid: chatId, message_id: content?.order + '' })), {
    manual: true,
    onSuccess: (data) => {
      const [, res] = data;
      if (res) {
        setStatus('none');
        message.success('操作成功');
      }
    },
  });

  return (
    <>
      {contextHolder}
      <div className="flex flex-1 items-center text-sm px-4">
        <div className="flex gap-3">
          <LikeOutlined
            className={classNames('cursor-pointer', { 'text-[#0C75FC]': status === 'like' })}
            onClick={async () => {
              if (status === 'like') {
                await cancel();
                return;
              }
              await feedback({ feedback_type: 'like' });
            }}
          />
          <Popover
            placement="bottom"
            autoAdjustOverflow
            destroyTooltipOnHide={true}
            content={<DislikeContent setFeedbackOpen={setFeedbackOpen} feedback={feedback} list={list || []} loading={loading} />}
            trigger="click"
            open={feedbackOpen}
          >
            <DislikeOutlined
              className={classNames('cursor-pointer', {
                'text-[#0C75FC]': status === 'unlike',
              })}
              onClick={async () => {
                if (status === 'unlike') {
                  await cancel();
                  return;
                }
                await getReasonList();
              }}
            />
          </Popover>
        </div>
        <Divider type="vertical" />
        <CopyOutlined className="cursor-pointer" onClick={() => onCopyContext(content.context)} />
      </div>
    </>
  );
};

export default Feedback;
