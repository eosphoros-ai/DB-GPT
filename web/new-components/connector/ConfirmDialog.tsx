import { Button, Modal, Progress, Space, Typography } from 'antd';
import React, { useEffect, useState } from 'react';
import { PendingConfirmation } from './types';

interface ConfirmDialogProps {
  confirmation: PendingConfirmation | null;
  onApprove: () => void;
  onDeny: () => void;
  onDismiss: () => void;
}

const { Text, Title } = Typography;

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({ confirmation, onApprove, onDeny, onDismiss }) => {
  const [remaining, setRemaining] = useState<number>(0);

  useEffect(() => {
    if (!confirmation) return;

    setRemaining(confirmation.timeout);

    const timer = setInterval(() => {
      setRemaining(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          onDeny();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [confirmation?.confirm_id]);

  if (!confirmation) return null;

  const percent = Math.round((remaining / confirmation.timeout) * 100);

  return (
    <Modal
      open
      mask={false}
      maskClosable={false}
      closable
      onCancel={onDismiss}
      footer={null}
      title={
        <Title level={5} style={{ margin: 0 }}>
          工具执行确认
        </Title>
      }
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        top: 'auto',
        margin: 0,
        paddingBottom: 0,
      }}
      width={360}
    >
      <Space direction='vertical' size='small' style={{ width: '100%' }}>
        <div>
          <Text type='secondary'>工具名称：</Text>
          <Text strong>{confirmation.tool_name}</Text>
        </div>
        <div>
          <Text type='secondary'>参数摘要：</Text>
          <Text>{confirmation.args_summary}</Text>
        </div>
        <div>
          <Text>{confirmation.message}</Text>
        </div>
        <Progress
          percent={percent}
          showInfo={false}
          strokeColor={percent > 30 ? '#52c41a' : '#ff4d4f'}
          size='small'
        />
        <Text type='secondary' style={{ fontSize: 12 }}>
          剩余 {remaining} 秒后自动拒绝
        </Text>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button danger onClick={onDeny}>
            拒绝
          </Button>
          <Button type='primary' onClick={onApprove} style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}>
            确认执行
          </Button>
        </Space>
      </Space>
    </Modal>
  );
};

export default ConfirmDialog;
