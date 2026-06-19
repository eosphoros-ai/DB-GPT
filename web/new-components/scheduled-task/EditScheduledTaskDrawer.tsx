import { ChatContext } from '@/app/chat-context';
import { renderModelIcon } from '@/components/chat/header/model-selector';
import { useScheduledTask } from '@/hooks/use-scheduled-task';
import type { TaskResponse } from '@/types/scheduled-task';
import { Button, Drawer, Form, Input, Select, Space, message } from 'antd';
import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import CronInput from './CronInput';

interface EditScheduledTaskDrawerProps {
  open: boolean;
  onClose: () => void;
  /** Task to edit */
  task: TaskResponse | null;
  /** Callback after a successful save (e.g. refresh the list) */
  onSaved: () => void;
}

const EditScheduledTaskDrawer: React.FC<EditScheduledTaskDrawerProps> = ({ open, onClose, task, onSaved }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [cron, setCron] = useState('0 9 * * *');
  const [submitting, setSubmitting] = useState(false);
  const { updateTask } = useScheduledTask();
  const { modelList } = useContext(ChatContext);

  // Sync form and cron when task changes
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
      open={open}
      onClose={onClose}
      destroyOnClose
      width={460}
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

        <Form.Item label={t('scheduled.save.freqLabel')} required>
          <CronInput value={cron} onChange={setCron} />
        </Form.Item>
      </Form>
    </Drawer>
  );
};

export default EditScheduledTaskDrawer;
