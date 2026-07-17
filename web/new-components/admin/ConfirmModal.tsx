import { Alert, Button, Input, Modal, Space, Typography } from 'antd';
import { useEffect, useState } from 'react';

export interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  impact?: string;
  impactItems?: { label: string; value: string }[];
  requireReason?: boolean;
  confirmText?: string;
  onConfirm: (reason?: string) => Promise<void>;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  description,
  impact,
  impactItems = [],
  requireReason = false,
  confirmText = '确认执行',
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setReason('');
      setSubmitting(false);
      setSubmitError(null);
    }
  }, [open]);

  const handleConfirm = async () => {
    const normalizedReason = reason.trim();
    if (requireReason && !normalizedReason) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await onConfirm(normalizedReason || undefined);
    } catch {
      setSubmitError('操作失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title={title}
      onCancel={submitting ? undefined : onCancel}
      footer={
        <Space>
          <Button disabled={submitting} onClick={onCancel}>
            取消
          </Button>
          <Button
            danger
            disabled={requireReason && !reason.trim()}
            loading={submitting}
            onClick={() => void handleConfirm()}
            type='primary'
          >
            {confirmText}
          </Button>
        </Space>
      }
      destroyOnHidden
      maskClosable={!submitting}
    >
      <Space className='w-full' direction='vertical' size={16}>
        <Typography.Paragraph className='mb-0 text-sm'>{description}</Typography.Paragraph>
        {submitError && <Alert message={submitError} type='error' showIcon />}
        {impact && <Alert message={impact} type='warning' showIcon />}
        {impactItems.length > 0 && (
          <div className='max-h-40 overflow-auto border-0 border-l-2 border-solid border-amber-400 pl-3'>
            {impactItems.map(item => (
              <div className='flex gap-3 py-1 text-sm' key={`${item.label}-${item.value}`}>
                <Typography.Text type='secondary' className='w-28 shrink-0'>
                  {item.label}
                </Typography.Text>
                <Typography.Text className='break-all'>{item.value}</Typography.Text>
              </div>
            ))}
          </div>
        )}
        {requireReason && (
          <div>
            <Typography.Text className='mb-2 block text-sm'>操作原因</Typography.Text>
            <Input.TextArea
              autoFocus
              maxLength={512}
              placeholder='请输入操作原因'
              rows={3}
              showCount
              value={reason}
              onChange={event => setReason(event.target.value)}
            />
          </div>
        )}
      </Space>
    </Modal>
  );
}

export default ConfirmModal;
