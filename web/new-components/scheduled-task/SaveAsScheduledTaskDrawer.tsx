import { useConnectors } from '@/hooks/use-connector-api';
import { useScheduledTask } from '@/hooks/use-scheduled-task';
import type { ChatReplayPayload } from '@/types/scheduled-task';
import { Button, Drawer, Form, Input, Space, Tag, Typography, message } from 'antd';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import CronInput from './CronInput';

const { Title, Text } = Typography;

/** Read the logged-in user's display name (nick_name) for creator display. */
function getCreatorName(): string | undefined {
  try {
    const raw = localStorage.getItem('__db_gpt_uinfo_key');
    if (!raw) return undefined;
    const info = JSON.parse(raw);
    return info?.nick_name || info?.real_name || info?.user_name || undefined;
  } catch {
    return undefined;
  }
}

interface SaveAsScheduledTaskDrawerProps {
  open: boolean;
  onClose: () => void;
  /** Current conversation snapshot, built by the home page buildSnapshot */
  snapshot: ChatReplayPayload;
  /** Default task name; falls back to the first 30 chars of user_input */
  defaultName?: string;
}

const SaveAsScheduledTaskDrawer: React.FC<SaveAsScheduledTaskDrawerProps> = ({
  open,
  onClose,
  snapshot,
  defaultName,
}) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [cron, setCron] = useState('0 9 * * *');
  const [submitting, setSubmitting] = useState(false);
  const { createTask } = useScheduledTask();
  const { connectors } = useConnectors();

  /** connector id → display_name map */
  const connectorNameMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of connectors) {
      m.set(c.id, c.display_name);
    }
    return m;
  }, [connectors]);

  const onSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const resp = await createTask({
        task_name: values.task_name,
        description: values.description,
        cron_expression: cron,
        payload: snapshot,
        creator_name: getCreatorName(),
      });
      message.success(t('scheduled.msg.created', { time: resp.next_run_time ?? t('scheduled.msg.createComingSoon') }));
      onClose();
    } catch (e: any) {
      // antd form validation rejects with errorFields; no need to show a message
      if (e?.errorFields) return;
      message.error(e?.message ?? t('scheduled.msg.saveFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  const ext = (snapshot.ext_info ?? {}) as Record<string, any>;

  return (
    <Drawer
      title={t('scheduled.save.title')}
      open={open}
      onClose={onClose}
      destroyOnClose
      width={460}
      footer={
        <Space style={{ float: 'right' }}>
          <Button onClick={onClose}>{t('scheduled.save.cancel')}</Button>
          <Button type='primary' loading={submitting} onClick={onSubmit}>
            {t('scheduled.save.submit')}
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout='vertical'
        initialValues={{
          task_name: defaultName ?? snapshot.user_input?.slice(0, 30) ?? '',
          description: '',
        }}
      >
        <Form.Item
          label={t('scheduled.save.nameLabel')}
          name='task_name'
          rules={[
            { required: true, message: t('scheduled.save.nameRequired') },
            { max: 256, message: t('scheduled.save.nameMax') },
          ]}
        >
          <Input placeholder={t('scheduled.save.namePlaceholder')} />
        </Form.Item>

        <Form.Item label={t('scheduled.save.descLabel')} name='description'>
          <Input.TextArea rows={2} placeholder={t('scheduled.save.descPlaceholder')} />
        </Form.Item>

        <Form.Item label={t('scheduled.save.freqLabel')} required>
          <CronInput value={cron} onChange={setCron} />
        </Form.Item>
      </Form>

      <Title level={5} style={{ marginTop: 16 }}>
        {t('scheduled.save.envTitle')}
      </Title>
      <div className='space-y-1 text-sm text-gray-600 dark:text-gray-300'>
        <div>
          {t('scheduled.save.envModel')}
          <Text code>{snapshot.model_name ?? t('scheduled.detail.modelDefault')}</Text>
        </div>
        <div>
          {t('scheduled.save.envQuestion')}
          <Text>{snapshot.user_input}</Text>
        </div>
        {ext.skill_id && (
          <div>
            {t('scheduled.save.envSkill')}
            <Tag color='blue'>{String(ext.skill_id)}</Tag>
          </div>
        )}
        {(() => {
          // Merge connector_ids and mcp_ids and display them together as MCP
          const ids: string[] = [
            ...(Array.isArray(ext.connector_ids) ? ext.connector_ids : []),
            ...(Array.isArray(ext.mcp_ids) ? ext.mcp_ids : []),
          ];
          if (ids.length === 0) return null;
          return (
            <div>
              {t('scheduled.save.envMcp')}
              {ids.map((id: string) => (
                <Tag key={id} color='green'>
                  {connectorNameMap.get(id) || id}
                </Tag>
              ))}
            </div>
          );
        })()}
      </div>
    </Drawer>
  );
};

export default SaveAsScheduledTaskDrawer;
