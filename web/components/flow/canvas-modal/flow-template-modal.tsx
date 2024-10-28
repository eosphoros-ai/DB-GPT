import { getFlowTemplates } from '@/client/api';
import CanvasWrapper from '@/pages/construct/flow/canvas/index';
import type { TableProps } from 'antd';
import { Button, Modal, Space, Table } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

type Props = {
  isFlowTemplateModalOpen: boolean;
  setIsFlowTemplateModalOpen: (value: boolean) => void;
};

interface DataType {
  key: string;
  name: string;
  age: number;
  address: string;
  tags: string[];
}

export const FlowTemplateModal: React.FC<Props> = ({ isFlowTemplateModalOpen, setIsFlowTemplateModalOpen }) => {
  const { t } = useTranslation();
  const [dataSource, setDataSource] = useState([]);

  const onTemplateImport = (record: DataType) => {
    if (record?.name) {
      localStorage.setItem('importFlowData', JSON.stringify(record));
      CanvasWrapper();
      setIsFlowTemplateModalOpen(false);
    }
  };

  const columns: TableProps<DataType>['columns'] = [
    {
      title: t('Template_Name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('Template_Label'),
      dataIndex: 'label',
      key: 'label',
    },
    {
      title: t('Template_Description'),
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: t('Template_Action'),
      key: 'action',
      render: (_, record) => (
        <Space size='middle'>
          <Button
            type='link'
            onClick={() => {
              onTemplateImport(record);
            }}
            block
          >
            {t('Import_From_Template')}
          </Button>
        </Space>
      ),
    },
  ];

  useEffect(() => {
    getFlowTemplates().then(res => {
      console.log(res);
      setDataSource(res?.data?.data?.items);
    });
  }, []);

  return (
    <>
      <Modal
        className='w-[700px]'
        title={t('Import_From_Template')}
        open={isFlowTemplateModalOpen}
        onCancel={() => setIsFlowTemplateModalOpen(false)}
        cancelButtonProps={{ className: 'hidden' }}
        okButtonProps={{ className: 'hidden' }}
      >
        <Table className='w-full' dataSource={dataSource} columns={columns} />;
      </Modal>
    </>
  );
};
