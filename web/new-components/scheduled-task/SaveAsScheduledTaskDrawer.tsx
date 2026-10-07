import { useConnectors } from '@/hooks/use-connector-api';
import { useScheduledTask } from '@/hooks/use-scheduled-task';
import { AttachmentMessageGroup, scheduledTaskFiles } from '@/modules/session-files';
import type { ChatReplayPayload, DashboardRefreshPayload, TaskResponse } from '@/types/scheduled-task';
import { Button, Drawer, Form, Input, Result, Space, Tag, Typography, message } from 'antd';
import dayjs from 'dayjs';
import { useRouter } from 'next/router';
import React, { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import CronInput from './CronInput';
import DashboardTaskContext from './DashboardTaskContext';

const { Title, Text } = Typography;

/** 读取当前登录用户的显示名称(nick_name),用于创建人展示。 */
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

type SaveAsScheduledTaskDrawerProps = {
  open: boolean;
  onClose: () => void;
  /** 当前对话快照，由主页 buildSnapshot 构造 */
  /** 默认任务名称，不传则截取 user_input 前 30 字符 */
  defaultName?: string;
  beforeCreate?: () => Promise<void>;
} & (
  | { snapshot: ChatReplayPayload; dashboard?: never }
  | { snapshot?: never; dashboard: DashboardRefreshPayload & { title: string } }
);

const SaveAsScheduledTaskDrawer: React.FC<SaveAsScheduledTaskDrawerProps> = ({
  open,
  onClose,
  snapshot,
  defaultName,
  dashboard,
  beforeCreate,
}) => {
  const router = useRouter();
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [cron, setCron] = useState('0 9 * * *');
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const [createdTask, setCreatedTask] = useState<TaskResponse | null>(null);
  const { createTask } = useScheduledTask();
  const { connectors } = useConnectors();

  /** connector id → display_name 映射 */
  const connectorNameMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of connectors) {
      m.set(c.id, c.display_name);
    }
    return m;
  }, [connectors]);

  const onSubmit = async () => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      await beforeCreate?.();
      const binding = dashboard
        ? {
            task_type: 'dashboard_refresh' as const,
            payload: {
              dashboard_id: dashboard.dashboard_id,
              filters: dashboard.filters,
              publish_after_refresh: false,
            },
          }
        : { task_type: 'chat_replay' as const, payload: snapshot! };
      const resp = await createTask({
        task_name: values.task_name,
        description: values.description,
        cron_expression: cron,
        ...binding,
        creator_name: getCreatorName(),
      });
      if (dashboard) {
        setCreatedTask(resp);
      } else {
        message.success(
          t('scheduled.msg.created', { time: resp.next_run_time ?? t('scheduled.msg.createComingSoon') }),
        );
        onClose();
      }
    } catch (e: any) {
      // antd form 校验失败时 reject 带 errorFields，不需要弹 message
      if (e?.errorFields) return;
      message.error(e?.message ?? t('scheduled.msg.saveFailed'));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const ext = (snapshot?.ext_info ?? {}) as Record<string, any>;
  const freezingFiles = scheduledTaskFiles(snapshot?.ext_info);

  if (createdTask) {
    return (
      <Drawer title='定时任务' aria-label='定时任务已创建' open={open} onClose={onClose} width={460} zIndex={1600}>
        <Result
          status='success'
          title='定时任务已创建'
          subTitle={
            createdTask.next_run_time
              ? `下次执行：${dayjs(createdTask.next_run_time).format('YYYY-MM-DD HH:mm:ss')}`
              : '已保存并启用，可在任务详情查看执行状态。'
          }
          extra={
            <Space direction='vertical'>
              <Button
                type='primary'
                onClick={() => {
                  onClose();
                  void router.push(`/construct/scheduled-tasks/${createdTask.task_id}/`);
                }}
              >
                查看任务及执行记录
              </Button>
              <Button onClick={onClose}>完成</Button>
            </Space>
          }
        />
        <p className='text-center text-sm text-gray-500'>也可从左侧「定时任务」统一管理。</p>
      </Drawer>
    );
  }

  return (
    <Drawer
      title={t('scheduled.save.title')}
      aria-label={t('scheduled.save.title')}
      open={open}
      onClose={() => {
        if (!submittingRef.current) onClose();
      }}
      closable={!submitting}
      maskClosable={!submitting}
      destroyOnClose
      width={460}
      zIndex={1600}
      footer={
        <Space style={{ float: 'right' }}>
          <Button disabled={submitting} onClick={onClose}>
            {t('scheduled.save.cancel')}
          </Button>
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
          task_name: defaultName ?? snapshot?.user_input?.slice(0, 30) ?? '',
          description: '',
        }}
      >
        <Form.Item
          label={t('scheduled.save.nameLabel')}
          name='task_name'
          rules={[
            { required: true, whitespace: true, message: t('scheduled.save.nameRequired') },
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

      {dashboard ? (
        <DashboardTaskContext payload={dashboard} title={dashboard.title} />
      ) : (
        <>
          <Title level={5} style={{ marginTop: 16 }}>
            {t('scheduled.save.envTitle')}
          </Title>
          <div className='space-y-1 text-sm text-gray-600 dark:text-gray-300'>
            <div>
              {t('scheduled.save.envModel')}
              <Text code>{snapshot?.model_name ?? t('scheduled.detail.modelDefault')}</Text>
            </div>
            <div>
              {t('scheduled.save.envQuestion')}
              <Text>{snapshot?.user_input}</Text>
            </div>
            {freezingFiles.length > 0 && (
              <div className='mt-2'>
                <div className='mb-1 text-xs text-gray-400'>将冻结以下附件（创建后与当前会话解耦）:</div>
                <AttachmentMessageGroup files={freezingFiles} />
              </div>
            )}
            {ext.skill_id && (
              <div>
                {t('scheduled.save.envSkill')}
                <Tag color='blue'>{String(ext.skill_id)}</Tag>
              </div>
            )}
            {(() => {
              // 合并 connector_ids 和 mcp_ids，统一显示为 MCP
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
        </>
      )}
    </Drawer>
  );
};

export default SaveAsScheduledTaskDrawer;
