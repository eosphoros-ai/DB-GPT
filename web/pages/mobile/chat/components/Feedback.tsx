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

  // Copy reply
  const onCopyContext = async (context: any) => {
    const pureStr = context?.replace(/\trelations:.*/g, '');
    const result = copy(chatDialogRef.current?.textContent || pureStr);
    if (result) {
      if (pureStr) {
        message.success('Copied successfully');
      } else {
        message.warning('Nothing to copy');
      }
    } else {
      message.error('Copy failed');
    }
  };

  // Like or dislike
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
        message.success('Feedback submitted');
        setFeedbackOpen(false);
      },
    },
  );

  // Cancel feedback
  const { run: cancel } = useRequest(
    async () => await apiInterceptors(cancelFeedback({ conv_uid: conv_uid, message_id: content?.order + '' })),
    {
      manual: true,
      onSuccess: data => {
        const [, res] = data;
        if (res) {
          setStatus('none');
          message.success('Done');
        }
      },
    },
  );

  // Feedback reason types
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

  // End topic
  const { run: stopTopicRun, loading: stopTopicLoading } = useRequest(
    async () => await apiInterceptors(stopTopic({ conv_id: conv_uid, round_index: 0 })),
    {
      manual: true,
      onSuccess: () => {
        message.success('Done');
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
          >
            End topic
          </Button>
        )}
      </div>
    </div>
  );
};

export default Feedback;
