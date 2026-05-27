import i18n from '@/app/i18n';
import { apiInterceptors, cancelFeedback, feedbackAdd, getFeedbackReasons, stopTopic } from '@/client/api';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { CopyOutlined, DislikeOutlined, LikeOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { App, Button, Divider } from 'antd';
import classNames from 'classnames';
import copy from 'copy-to-clipboard';
import React, { useContext, useState } from 'react';
import { MobileChatContext } from '..';
import DislikeDrawer from './DislikeDrawer';
import { useTranslation } from 'react-i18next';

interface Tags {
  reason: string;
  reason_type: string;
}

const Feedback: React.FC<{
  content: IChatDialogueMessageSchema;
  index: number;
  chatDialogRef: React.RefObject<HTMLDivElement>;
}> = ({ content, index, chatDialogRef }) => {
  const { conv_uid, history, scene } = useContext(MobileChatContext);
  const { message } = App.useApp();

  const [feedbackOpen, setFeedbackOpen] = useState<boolean>(false);
  const [status, setStatus] = useState<'like' | 'unlike' | 'none'>(content?.feedback?.feedback_type);
  const [list, setList] = useState<Tags[]>([]);

  // 复制回答
  const onCopyContext = async (context: any) => {
    const pureStr = context?.replace(/\trelations:.*/g, '');
    const result = copy(chatDialogRef.current?.textContent || pureStr);
    if (result) {
      if (pureStr) {
        message.success(i18n.t('copy_success'));
      } else {
        message.warning(i18n.t('copy_nothing'));
      }
    } else {
      message.error(i18n.t('copy_failed_generic'));
    }
  };

  // 点赞 or 踩
  const { run: feedback, loading } = useRequest(
    async (params: { feedback_type: string; reason_types?: string[]; remark?: string }) =>
      await apiInterceptors(
        feedbackAdd({
          conv_uid: conv_uid,
          message_id: content.order + '',
          feedback_type: params.feedback_type,
          reason_types: params.reason_types,
          remark: params.remark,
        }),
      ),
    {
      manual: true,
      onSuccess: data => {
        const [, res] = data;
        setStatus(res?.feedback_type);
        message.success(i18n.t('ui_0aaa810f'));
        setFeedbackOpen(false);
      },
    },
  );

  // 取消反馈
  const { run: cancel } = useRequest(
    async () => await apiInterceptors(cancelFeedback({ conv_uid: conv_uid, message_id: content?.order + '' })),
    {
      manual: true,
      onSuccess: data => {
        const [, res] = data;
        if (res) {
          setStatus('none');
          message.success(i18n.t('ui_33130f5c'));
        }
      },
    },
  );

  // 反馈原因类型
  const { run: getReasonList } = useRequest(async () => await apiInterceptors(getFeedbackReasons()), {
    manual: true,
    onSuccess: data => {
      const [, res] = data;
      setList(res || []);
      if (res) {
        setFeedbackOpen(true);
      }
    },
  });

  // 终止话题
  const { run: stopTopicRun, loading: stopTopicLoading } = useRequest(
    async () => await apiInterceptors(stopTopic({ conv_id: conv_uid, round_index: 0 })),
    {
      manual: true,
      onSuccess: () => {
        message.success(i18n.t('ui_33130f5c'));
      },
    },
  );

  return (
    <div className='flex items-center text-sm'>
      <div className='flex gap-3'>
        <LikeOutlined
          className={classNames('cursor-pointer', {
            'text-[#0C75FC]': status === 'like',
          })}
          onClick={async () => {
            if (status === 'like') {
              await cancel();
              return;
            }
            await feedback({ feedback_type: 'like' });
          }}
        />
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
        <DislikeDrawer
          open={feedbackOpen}
          setFeedbackOpen={setFeedbackOpen}
          list={list}
          feedback={feedback}
          loading={loading}
        />
      </div>
      <Divider type='vertical' />
      <div className='flex items-center gap-3'>
        <CopyOutlined className='cursor-pointer' onClick={() => onCopyContext(content.context)} />
        {history.length - 1 === index && scene === 'chat_agent' && (
          <Button
            loading={stopTopicLoading}
            size='small'
            onClick={async () => {
              await stopTopicRun();
            }}
            className='text-xs'
          >{i18n.t('ui_212ed895')}</Button>
        )}
      </div>
    </div>
  );
};

export default Feedback;
