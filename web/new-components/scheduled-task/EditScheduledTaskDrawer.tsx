import { ChatContext } from '@/app/chat-context';
import { renderModelIcon } from '@/components/chat/header/model-selector';
import { useScheduledTask } from '@/hooks/use-scheduled-task';
import type { TaskResponse } from '@/types/scheduled-task';
import { Button, Drawer, Form, Input, Select, Space, message } from 'antd';
import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import CronInput from './CronInput';
import DashboardTaskContext from './DashboardTaskContext';

interface EditScheduledTaskDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 要编辑的任务 */
  task: TaskResponse | null;
  /** 保存成功回调（用于刷新列表） */
  onSaved: () => void;
}

const EditScheduledTaskDrawer: React.FC<EditScheduledTaskDrawerProps> = ({ open, onClose, task, onSaved }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const { updateTask } = useScheduledTask();
  const { modelList } = useContext(ChatContext);
  const chatPayload = task?.task_type === 'chat_replay' ? task.payload : null;

  // 当 task 变化时同步表单和 cron
  useEffect(() => {
    if (task && open) {
      form.setFieldsValue({
        task_name: task.task_name,
        description: task.description ?? '',
        user_input: task.task_type === 'chat_replay' ? (task.payload?.user_input ?? '') : undefined,
        model_name: task.task_type === 'chat_replay' ? (task.payload?.model_name ?? undefined) : undefined,
        cron_expression: task.cron_expression,
      });
    }
  }, [task, form, open]);

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
      if (values.cron_expression !== task.cron_expression) {
        patch.cron_expression = values.cron_expression;
      }
      // Payload edits — only send when changed, so the backend skips the
      // payload merge entirely if the user only touched name/description/cron.
      if (task.task_type === 'chat_replay' && values.user_input !== (chatPayload?.user_input ?? '')) {
        patch.user_input = values.user_input;
      }
      if (
        task.task_type === 'chat_replay' &&
        (values.model_name ?? undefined) !== (chatPayload?.model_name ?? undefined)
      ) {
        patch.model_name = values.model_name || null;
      }
      await updateTask(task.task_id, patch);
      message.success(t('scheduled.msg.updated'));
      onSaved();
      onClose();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.message ?? t('scheduled.msg.updateFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Drawer
      title={t('scheduled.edit.title')}
      aria-label={t('scheduled.edit.title')}
      open={open}
      onClose={onClose}
      destroyOnClose
      width={460}
      zIndex={1600}
      footer={
        <Space style={{ float: 'right' }}>
          <Button onClick={onClose}>{t('scheduled.save.cancel')}</Button>
          <Button type='primary' loading={submitting} onClick={onSubmit}>
            {t('scheduled.edit.save')}
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

        {task?.task_type === 'chat_replay' && (
          <>
            <Form.Item
              label={t('scheduled.edit.rawQuestionLabel')}
              name='user_input'
              rules={[{ required: true, message: t('scheduled.edit.rawQuestionRequired') }]}
            >
              <Input.TextArea rows={3} placeholder={t('scheduled.edit.rawQuestionPlaceholder')} />
            </Form.Item>

            <Form.Item label={t('scheduled.edit.modelLabel')} name='model_name'>
              <Select
                allowClear
                placeholder={t('scheduled.edit.modelPlaceholder')}
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
          </>
        )}
        <Form.Item label={t('scheduled.save.freqLabel')} name='cron_expression' required>
          <CronInput />
        </Form.Item>
      </Form>
      {task?.task_type === 'dashboard_refresh' && <DashboardTaskContext payload={task.payload} />}
    </Drawer>
  );
};

export default EditScheduledTaskDrawer;
