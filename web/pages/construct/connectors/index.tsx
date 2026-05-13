import {
  useConnectors,
  useConnectorTypes,
  useCreateConnector,
  useDeleteConnector,
  useTestConnection,
  useUpdateConnector,
} from '@/hooks/use-connector-api';
import { ConnectorCard, ConnectorForm } from '@/new-components/connector';
import { ConnectorInstance, CreateConnectorRequest } from '@/new-components/connector/types';
import ConstructLayout from '@/new-components/layout/Construct';
import { PlusOutlined } from '@ant-design/icons';
import { Button, Col, Empty, Row, Spin, Typography, message } from 'antd';
import { useState } from 'react';

const { Title } = Typography;

function Connectors() {
  const { connectors, loading, refresh } = useConnectors();
  const { types: catalog, loading: catalogLoading } = useConnectorTypes();
  const { create, loading: creating } = useCreateConnector();
  const { update, loading: updating } = useUpdateConnector();
  const { remove, loading: deleting } = useDeleteConnector();
  const { test } = useTestConnection();

  const [formOpen, setFormOpen] = useState(false);
  const [editingConnector, setEditingConnector] = useState<ConnectorInstance | undefined>(undefined);

  const handleAdd = () => {
    setEditingConnector(undefined);
    setFormOpen(true);
  };

  const handleEdit = (connector: ConnectorInstance) => {
    setEditingConnector(connector);
    setFormOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await remove(id);
      message.success('连接器已删除');
      refresh();
    } catch {
      message.error('删除失败，请重试');
    }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await test(id);
      if (result.success) {
        message.success(result.message || '连接测试成功');
      } else {
        message.error(result.message || '连接测试失败');
      }
    } catch {
      message.error('连接测试失败，请检查配置');
    }
  };

  const handleSubmit = async (data: CreateConnectorRequest) => {
    try {
      if (editingConnector) {
        await update(editingConnector.id, data);
        message.success('连接器已更新');
      } else {
        await create(data);
        message.success('连接器已创建');
      }
      setFormOpen(false);
      setEditingConnector(undefined);
      refresh();
    } catch {
      message.error(editingConnector ? '更新失败，请重试' : '创建失败，请重试');
    }
  };

  const handleClose = () => {
    setFormOpen(false);
    setEditingConnector(undefined);
  };

  return (
    <ConstructLayout>
      <div className='relative h-screen w-full p-4 md:p-6 overflow-y-auto'>
        <div className='flex justify-between items-center mb-6'>
          <Title level={4} className='!mb-0'>
            连接器管理
          </Title>
          <Button
            className='border-none text-white bg-button-gradient'
            icon={<PlusOutlined />}
            onClick={handleAdd}
            loading={creating || updating}
          >
            添加连接器
          </Button>
        </div>

        <Spin spinning={loading || deleting}>
          {connectors.length === 0 && !loading ? (
            <Empty description='暂无连接器，点击"添加连接器"开始配置' className='mt-16' />
          ) : (
            <Row gutter={[16, 16]}>
              {connectors.map(connector => (
                <Col key={connector.id} xs={24} sm={12} md={8} lg={6}>
                  <ConnectorCard
                    connector={connector}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                    onTest={handleTest}
                  />
                </Col>
              ))}
            </Row>
          )}
        </Spin>

        <ConnectorForm
          open={formOpen}
          onClose={handleClose}
          onSubmit={handleSubmit}
          catalog={catalog}
          catalogLoading={catalogLoading}
          initialValues={editingConnector}
        />
      </div>
    </ConstructLayout>
  );
}

export default Connectors;
