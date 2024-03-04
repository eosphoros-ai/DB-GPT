import { apiInterceptors, deleteFlowById, newDialogue } from '@/client/api';
import { IFlow } from '@/types/flow';
import {
  CopyFilled,
  DeleteFilled,
  EditFilled,
  ExclamationCircleFilled,
  ExclamationCircleOutlined,
  MessageFilled,
  WarningOutlined,
} from '@ant-design/icons';
import { Modal, Tooltip } from 'antd';
import React, { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import FlowPreview from './preview-flow';
import { useRouter } from 'next/router';
import GptCard from '../common/gpt-card';
import { ChatContext } from '@/app/chat-context';
import qs from 'querystring';

interface FlowCardProps {
  flow: IFlow;
  deleteCallback: (uid: string) => void;
  onCopy: (flow: IFlow) => void;
}

const FlowCard: React.FC<FlowCardProps> = ({ flow, onCopy, deleteCallback }) => {
  const { model } = useContext(ChatContext);
  const { t } = useTranslation();
  const [modal, contextHolder] = Modal.useModal();
  const router = useRouter();

  async function deleteFlow() {
    const [, , res] = await apiInterceptors(deleteFlowById(flow.uid));
    if (res?.success) {
      deleteCallback && deleteCallback(flow.uid);
    }
  }

  function cardClick() {
    router.push('/flow/canvas?id=' + flow.uid);
  }

  const handleChat = async () => {
    const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_agent' }));
    if (res) {
      const queryStr = qs.stringify({
        scene: 'chat_flow',
        id: res.conv_uid,
        model: model,
        select_param: flow.uid,
      });
      router.push(`/chat?${queryStr}`);
    }
  };

  const handleDel = () => {
    modal.confirm({
      title: t('Tips'),
      icon: <WarningOutlined />,
      content: t('delete_flow_confirm'),
      okText: 'Yes',
      okType: 'danger',
      cancelText: 'No',
      async onOk() {
        deleteFlow();
      },
    });
  };

  return (
    <>
      {contextHolder}
      <GptCard
        className="w-[26rem] max-w-full"
        title={flow.name}
        desc={flow.description}
        tags={[
          { text: flow.source, color: flow.source === 'DBGPT-WEB' ? 'green' : 'blue', border: true },
          { text: flow.editable ? 'Editable' : 'Can not Edit', color: flow.editable ? 'green' : 'gray', border: true },
          {
            text: (
              <>
                {flow.error_message ? (
                  <Tooltip placement="bottom" title={flow.error_message}>
                    {flow.state}
                    <ExclamationCircleOutlined className="ml-1" />
                  </Tooltip>
                ) : (
                  flow.state
                )}
              </>
            ),
            color: flow.state === 'load_failed' ? 'red' : flow.state === 'running' ? 'green' : 'blue',
            border: true,
          },
        ]}
        operations={[
          {
            label: t('Chat'),
            children: <MessageFilled />,
            onClick: handleChat,
          },
          {
            label: t('Edit'),
            children: <EditFilled />,
            onClick: cardClick,
          },
          {
            label: t('Copy'),
            children: <CopyFilled />,
            onClick: () => {
              onCopy(flow);
            },
          },
          {
            label: t('Delete'),
            children: <DeleteFilled />,
            onClick: handleDel,
          },
        ]}
      >
        <div className="w-full h-40 shadow-[inset_0_0_16px_rgba(50,50,50,.05)]">
          <FlowPreview flowData={flow.flow_data} />
        </div>
      </GptCard>
    </>
  );
};

export default FlowCard;
