import { useConnectors } from '@/hooks/use-connector-api';
import { useScheduledTask } from '@/hooks/use-scheduled-task';
import type { ChatReplayPayload } from '@/types/scheduled-task';
import { Button, Drawer, Form, Input, Space, Tag, Typography, message } from 'antd';
import React, { useMemo, useState } from 'react';
import CronInput from './CronInput';

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

interface SaveAsScheduledTaskDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 当前对话快照，由主页 buildSnapshot 构造 */
  snapshot: ChatReplayPayload;
  /** 默认任务名称，不传则截取 user_input 前 30 字符 */
  defaultName?: string;
}

const SaveAsScheduledTaskDrawer: React.FC<SaveAsScheduledTaskDrawerProps> = ({
  open,
  onClose,
  snapshot,
  defaultName,
}) => {
  const [form] = Form.useForm();
  const [cron, setCron] = useState('0 9 * * *');
  const [submitting, setSubmitting] = useState(false);
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
      message.success(`已创建定时任务，下次执行 ${resp.next_run_time ?? '即将到来'}`);
      onClose();
    } catch (e: any) {
      // antd form 校验失败时 reject 带 errorFields，不需要弹 message
      if (e?.errorFields) return;
      message.error(e?.message ?? '保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  const ext = (snapshot.ext_info ?? {}) as Record<string, any>;

  return (
    <Drawer
      title='保存为定时任务'
      open={open}
      onClose={onClose}
      destroyOnClose
      width={460}
      footer={
        <Space style={{ float: 'right' }}>
          <Button onClick={onClose}>取消</Button>
          <Button type='primary' loading={submitting} onClick={onSubmit}>
            保存并启用
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
          label='任务名称'
          name='task_name'
          rules={[
            { required: true, message: '请输入任务名称' },
            { max: 256, message: '任务名称最多 256 个字符' },
          ]}
        >
          <Input placeholder='请输入定时任务名称' />
        </Form.Item>

        <Form.Item label='描述（可选）' name='description'>
          <Input.TextArea rows={2} placeholder='简要描述任务用途' />
        </Form.Item>

        <Form.Item label='执行频率' required>
          <CronInput value={cron} onChange={setCron} />
        </Form.Item>
      </Form>

      <Title level={5} style={{ marginTop: 16 }}>
        将复用本次对话的环境（只读）
      </Title>
      <div className='space-y-1 text-sm text-gray-600 dark:text-gray-300'>
        <div>
          模型：<Text code>{snapshot.model_name ?? '默认'}</Text>
        </div>
        <div>
          原始问题：<Text>{snapshot.user_input}</Text>
        </div>
        {ext.skill_id && (
          <div>
            技能：<Tag color='blue'>{String(ext.skill_id)}</Tag>
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
              MCP：
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
