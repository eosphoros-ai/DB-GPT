import { ApiOutlined, DeleteOutlined, EditOutlined, ScheduleOutlined } from '@ant-design/icons';
import { Button, Card, Popconfirm, Space, Tag } from 'antd';
import React from 'react';
import { ConnectorInstance, ConnectorStatus } from './types';

interface ConnectorCardProps {
  connector: ConnectorInstance;
  onEdit: (connector: ConnectorInstance) => void;
  onDelete: (id: string) => void;
  onTest?: (id: string) => void;
  onSchedule?: (connector: ConnectorInstance) => void;
}

const STATUS_COLOR: Record<ConnectorStatus, string> = {
  active: 'green',
  error: 'red',
  disconnected: 'default',
};

const STATUS_LABEL: Record<ConnectorStatus, string> = {
  active: '已连接',
  error: '错误',
  disconnected: '未连接',
};

const ConnectorCard: React.FC<ConnectorCardProps> = ({ connector, onEdit, onDelete, onTest, onSchedule }) => {
  return (
    <Card
      title={connector.display_name}
      extra={
        <Space>
          {onTest && (
            <Button
              type='text'
              icon={<ApiOutlined />}
              onClick={() => onTest(connector.id)}
              title='测试连接'
            />
          )}
          {onSchedule && (
            <Button
              type='text'
              icon={<ScheduleOutlined />}
              onClick={() => onSchedule(connector)}
              title='定时任务'
            />
          )}
          <Button
            type='text'
            icon={<EditOutlined />}
            onClick={() => onEdit(connector)}
          />
          <Popconfirm
            title='确认删除'
            description='确定要删除该连接器吗？'
            onConfirm={() => onDelete(connector.id)}
            okText='删除'
            cancelText='取消'
            okButtonProps={{ danger: true }}
          >
            <Button type='text' danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      }
      className='w-full'
    >
      <Space direction='vertical' size='small' className='w-full'>
        <div>
          <span className='text-gray-500 text-sm'>类型：</span>
          <span className='text-sm'>{connector.connector_type}</span>
        </div>
        <div>
          <span className='text-gray-500 text-sm'>状态：</span>
          <Tag color={STATUS_COLOR[connector.status]}>{STATUS_LABEL[connector.status]}</Tag>
        </div>
        {connector.created_at && (
          <div>
            <span className='text-gray-500 text-sm'>创建时间：</span>
            <span className='text-sm'>{connector.created_at}</span>
          </div>
        )}
      </Space>
    </Card>
  );
};

export default ConnectorCard;
