import { apiInterceptors, deleteFlowById } from '@/client/api';
import { IFlow } from '@/types/flow';
import { DeleteFilled, WarningOutlined } from '@ant-design/icons';
import { Modal } from 'antd';
import Link from 'next/link';
import React from 'react';
import { useTranslation } from 'react-i18next';

interface FlowCardProps {
  flow: IFlow;
  deleteCallback: (uid: string) => void;
}

const FlowCard: React.FC<FlowCardProps> = ({ flow, deleteCallback }) => {
  const { t } = useTranslation();
  const [modal, contextHolder] = Modal.useModal();

  async function deleteFlow() {
    const [res] = await apiInterceptors(deleteFlowById(flow.uid));
    deleteCallback && deleteCallback(flow.uid);
  }

  return (
    <>
      <Link href={`/flow/canvas?id=${flow.uid}`}>
        <div className="relative flex flex-col p-4 w-72 h-32 rounded justify-between cursor-pointer text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1">
          <div className="flex items-center">
            <div className="flex flex-col">
              <h2 className="text-lg font-semibold">{flow.name}</h2>
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
      </Link>
      {contextHolder}
    </>
  );
};

export default FlowCard;
