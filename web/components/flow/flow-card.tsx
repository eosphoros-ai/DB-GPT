import { apiInterceptors, deleteFlowById } from '@/client/api';
import { IFlow } from '@/types/flow';
import { DeleteFilled, WarningOutlined } from '@ant-design/icons';
import { Divider, Modal } from 'antd';
import React from 'react';
import { useTranslation } from 'react-i18next';
import FlowPreview from './preview-flow';
import { useRouter } from 'next/router';
import GptCard from '../common/gpt-card';

interface FlowCardProps {
  flow: IFlow;
  deleteCallback: (uid: string) => void;
}

const FlowCard: React.FC<FlowCardProps> = ({ flow, deleteCallback }) => {
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

  return (
    <>
      {contextHolder}
      <GptCard
        className="w-96"
        title={flow.name}
        desc={flow.description}
        tags={['GPT-3', { text: 'Python', color: 'green' }]}
        onClick={cardClick}
        operations={[
          {
            label: t('Delete'),
            children: <DeleteFilled className="text-red-500" />,
            onClick: () => {
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
            },
          },
        ]}
      >
        <div className="w-full h-[150px]">
          <FlowPreview flowData={flow.flow_data} />
        </div>
      </GptCard>
    </>
  );
};

export default FlowCard;
