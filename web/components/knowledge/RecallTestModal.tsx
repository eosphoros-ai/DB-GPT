import i18n from '@/app/i18n';
import { apiInterceptors, recallMethodOptions, recallTest, recallTestRecommendQuestion } from '@/client/api';
import MarkDownContext from '@/new-components/common/MarkdownContext';
import { ISpace, RecallTestProps } from '@/types/knowledge';
import { SettingOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Card, Empty, Form, Input, InputNumber, Modal, Popover, Select, Spin, Tag } from 'antd';
import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

type RecallTestModalProps = {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  space: ISpace;
};

// const tagColors = ['magenta', 'orange', 'geekblue', 'purple', 'cyan', 'green'];

const RecallTestModal: React.FC<RecallTestModalProps> = ({ open, setOpen, space }) => {
  const [form] = Form.useForm();
  const [extraForm] = Form.useForm();

  // 获取推荐问题
  const { run: questionsRun } = useRequest(
    // const { data: questions = [], run: questionsRun } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(recallTestRecommendQuestion(space.name + ''));
      return res ?? [];
    },
    {
      manual: true,
    },
  );

  // 召回方法选项
  const { data: options = [], run: optionsRun } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(recallMethodOptions(space.name + ''));
      return res ?? [];
    },
    {
      manual: true,
      onSuccess: data => {
        extraForm.setFieldValue('recall_retrievers', data);
      },
    },
  );

  useEffect(() => {
    if (open) {
      // questionsRun();
      optionsRun();
    }
  }, [open, optionsRun, questionsRun]);

  // 召回测试
  const {
    run: recallTestRun,
    data: resultList = [],
    loading,
  } = useRequest(
    async (props: RecallTestProps) => {
      const [, res] = await apiInterceptors(recallTest({ ...props }, space.name + ''));
      return res ?? [];
    },
    {
      manual: true,
    },
  );
  const onTest = async () => {
    form.validateFields().then(async values => {
      const extraVal = extraForm.getFieldsValue();
      await recallTestRun({ recall_top_k: 1, recall_retrievers: options, ...values, ...extraVal });
    });
  };

  return (
    <Modal
      title={i18n.t('Recall_test')}
      width={'60%'}
      open={open}
      footer={false}
      onCancel={() => setOpen(false)}
      centered
      destroyOnClose={true}
    >
      <Card
        title={i18n.t('recall_configuration')}
        size='small'
        className='my-4'
        extra={
          <Popover
            placement='bottomRight'
            trigger='hover'
            title={i18n.t('vector_retrieval_settings')}
            content={
              <Form
                form={extraForm}
                initialValues={{
                  recall_top_k: 1,
                }}
              >
                <Form.Item label='Topk' tooltip={i18n.t('the_top_k_vectors')} name='recall_top_k'>
                  <InputNumber placeholder={i18n.t('Please_Input')} className='w-full' />
                </Form.Item>
                <Form.Item label={i18n.t('recall_method')} name='recall_retrievers'>
                  <Select
                    mode='multiple'
                    options={options.map(item => {
                      return { label: item, value: item };
                    })}
                    className='w-full'
                    allowClear
                    disabled
                  />
                </Form.Item>
                <Form.Item label={i18n.t('score_threshold')} name='recall_score_threshold'>
                  <InputNumber placeholder={i18n.t('Please_Input')} className='w-full' step={0.1} />
                </Form.Item>
              </Form>
            }
          >
            <SettingOutlined className='text-lg' />
          </Popover>
        }
      >
        <Form form={form} layout='vertical' onFinish={onTest}>
          <Form.Item
            label={i18n.t('test_question')}
            required={true}
            name='question'
            rules={[{ required: true, message: i18n.t('enter_a_test_question') }]}
            className='m-0 p-0'
          >
            <div className='flex w-full items-center gap-8'>
              <Input placeholder={i18n.t('enter_a_test_question')} autoComplete='off' allowClear className='w-1/2' />
              <Button type='primary' htmlType='submit'>{i18n.t('test')}</Button>
            </div>
          </Form.Item>

          {/* {questions?.length > 0 && (
              <Col span={16}>
                <Form.Item label="推荐问题" tooltip="点击选择，自动填入">
                  <div className="flex flex-wrap gap-2">
                    {questions.map((item, index) => (
                      <Tag
                        color={tagColors[index]}
                        key={item}
                        className="cursor-pointer"
                        onClick={() => {
                          form.setFieldValue('question', item);
                        }}
                      >
                        {item}
                      </Tag>
                    ))}
                  </div>
                </Form.Item>
              </Col>
            )} */}
        </Form>
      </Card>
      <Card title={i18n.t('recall_results')} size='small'>
        <Spin spinning={loading}>
          {resultList.length > 0 ? (
            <div
              className='flex flex-col overflow-y-auto'
              style={{
                height: '45vh',
              }}
            >
              {resultList.map(item => (
                <Card
                  title={
                    <div className='flex items-center'>
                      <Tag color='blue'># {item.chunk_id}</Tag>
                      {item.metadata.source}
                    </div>
                  }
                  extra={
                    <div className='flex items-center gap-2'>
                      <span className='font-semibold'>score:</span>
                      <span className='text-blue-500'>{item.score}</span>
                    </div>
                  }
                  key={item.chunk_id}
                  size='small'
                  className='mb-4 border-gray-500 shadow-md'
                >
                  <MarkDownContext>{item.content}</MarkDownContext>
                </Card>
              ))}
            </div>
          ) : (
            <Empty />
          )}
        </Spin>
      </Card>
    </Modal>
  );
};

export default RecallTestModal;
