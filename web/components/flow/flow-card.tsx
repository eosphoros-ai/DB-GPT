import { apiInterceptors, deleteFlowById } from '@/client/api';
import { IFlow } from '@/types/flow';
import { DeleteFilled, WarningOutlined } from '@ant-design/icons';
import { Divider, Modal } from 'antd';
import React from 'react';
import { useTranslation } from 'react-i18next';
import FlowPreview from './preview-flow';
import { useRouter } from 'next/router';

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
      <div
        className="relative flex flex-col p-4 w-96 rounded justify-between cursor-pointer text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1"
        onClick={cardClick}
      >
        <div className="flex items-center">
          <div className="flex flex-col w-full">
            <h2 className="text-lg font-semibold">{flow.name}</h2>
            <h3 className="text-stone-500 text-sm line-clamp-2">{flow.description}</h3>
            <Divider className="my-2" />
            <div className="w-full h-[150px]">
              <FlowPreview flowData={flow.flow_data} />
            </div>
          </div>
        </div>
        <DeleteFilled
          className="absolute top-4 right-4 text-[#ff1b2e] !text-lg"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
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
          }}
        />
      </div>
      {contextHolder}
    </>
  );
};

export default FlowCard;
