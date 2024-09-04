import { IFlowData, IFlowUpdateParam } from '@/types/flow';
import { Button, Form, Input, Modal, Space, message,Table  } from 'antd';
import { useTranslation } from 'react-i18next';
import { ReactFlowInstance } from 'reactflow';
import type { TableProps } from 'antd';

import { getFlowTemplates } from '@/client/api';

import { useEffect, useState } from 'react';

import CanvasWrapper from '@/pages/construct/flow/canvas/index';

type Props = {
  isTemplateFlowModalOpen: boolean;
  setIsTemplateFlowModalOpen: (value: boolean) => void;
};

interface DataType {
  key: string;
  name: string;
  age: number;
  address: string;
  tags: string[];
}
export const TemplateFlowModa: React.FC<Props> = ({
  isTemplateFlowModalOpen,
  setIsTemplateFlowModalOpen,
}) => {
  const { t } = useTranslation();
  const [dataSource, setDataSource] = useState([]);
  const ReferenceTemplate = (record: any,) => {
    if (record?.name) {
      localStorage.setItem('importFlowData', JSON.stringify(record));
      CanvasWrapper()
      setIsTemplateFlowModalOpen(false);
    }
  }
  const columns: TableProps<DataType>['columns'] = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Space  size="middle">
          <Button type="link" onClick={()=>{ReferenceTemplate(record)}} block>
          {t('BringTemplate')}  
          </Button>
        </Space>
      ),
    },
  ];
  useEffect(() => {
    getFlowTemplates().then(res => {
      console.log(res);
      setDataSource(res?.data?.data?.items)
    });
  },[])
  return (
    <>
      <Modal
        title={t('LeadTemplate')}
        open={isTemplateFlowModalOpen}
        onCancel={() => setIsTemplateFlowModalOpen(false)}
        cancelButtonProps={{ className: 'hidden' }}
        okButtonProps={{ className: 'hidden' }}
      >
        <Table dataSource={dataSource} columns={columns} />;
      </Modal>
    </>
  );
};
