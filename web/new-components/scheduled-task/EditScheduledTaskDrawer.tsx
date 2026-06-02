import { ChatContext } from '@/app/chat-context';
import { renderModelIcon } from '@/components/chat/header/model-selector';
import { useScheduledTask } from '@/hooks/use-scheduled-task';
import type { TaskResponse } from '@/types/scheduled-task';
import { Button, Drawer, Form, Input, Select, Space, message } from 'antd';
import React, { useContext, useEffect, useState } from 'react';
import CronInput from './CronInput';

interface EditScheduledTaskDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 要编辑的任务 */
  task: TaskResponse | null;
  /** 保存成功回调（用于刷新列表） */
  onSaved: () => void;
}

const EditScheduledTaskDrawer: React.FC<EditScheduledTaskDrawerProps> = ({ open, onClose, task, onSaved }) => {
  const [form] = Form.useForm();
  const [cron, setCron] = useState('0 9 * * *');
  const [submitting, setSubmitting] = useState(false);
  const { updateTask } = useScheduledTask();
  const { modelList } = useContext(ChatContext);

  // 当 task 变化时同步表单和 cron
  useEffect(() => {
    if (task) {
      form.setFieldsValue({
        task_name: task.task_name,
        description: task.description ?? '',
        user_input: task.payload?.user_input ?? '',
        model_name: task.payload?.model_name ?? undefined,
      });
      setCron(task.cron_expression || '0 9 * * *');
    }
  }, [task, form]);

  const onSubmit = async () => {
    if (!task) return;
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      // Only include cron_expression when it actually changed,
      // to avoid unnecessary scheduler reschedule (which triggers
      // APScheduler pickle serialisation).
      const patch: Record<string, any> = {
        task_name: values.task_name,
        description: values.description || null,
      };
      if (cron !== task.cron_expression) {
        patch.cron_expression = cron;
      }
      // Payload edits — only send when changed, so the backend skips the
      // payload merge entirely if the user only touched name/description/cron.
      if (values.user_input !== (task.payload?.user_input ?? '')) {
        patch.user_input = values.user_input;
      }
      if ((values.model_name ?? undefined) !== (task.payload?.model_name ?? undefined)) {
        patch.model_name = values.model_name || null;
      }
      await updateTask(task.task_id, patch);
      message.success('定时任务已更新');
      onSaved();
      onClose();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.message ?? '更新失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Drawer
      title='编辑定时任务'
      open={open}
      onClose={onClose}
      destroyOnClose
      width={460}
      footer={
        <Space style={{ float: 'right' }}>
          <Button onClick={onClose}>取消</Button>
          <Button type='primary' loading={submitting} onClick={onSubmit}>
            保存
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout='vertical'
        initialValues={{
          task_name: task?.task_name ?? '',
          description: task?.description ?? '',
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

        <Form.Item
          label='原始问题'
          name='user_input'
          rules={[{ required: true, message: '请输入原始问题' }]}
        >
          <Input.TextArea rows={3} placeholder='定时执行时回放的原始问题' />
        </Form.Item>

        <Form.Item label='执行模型' name='model_name'>
          <Select
            allowClear
            placeholder='选择执行模型（留空则用默认）'
            popupMatchSelectWidth={false}
            options={(modelList ?? []).map(item => ({
              value: item,
              label: (
                <div className='flex items-center'>
                  {renderModelIcon(item)}
                  <span className='ml-2'>{item}</span>
                </div>
              ),
            }))}
          />
        </Form.Item>

        <Form.Item label='执行频率' required>
          <CronInput value={cron} onChange={setCron} />
        </Form.Item>
      </Form>
    </Drawer>
  );
};

export default EditScheduledTaskDrawer;
