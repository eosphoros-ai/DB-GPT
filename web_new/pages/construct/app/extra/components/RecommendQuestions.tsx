import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Switch } from 'antd';
import cls from 'classnames';
import React, { useEffect } from 'react';

import styles from '../styles.module.css';

interface RecommendQuestion {
  question: string;
  valid: boolean;
}
interface FormRecommendQuestion {
  recommend_questions: RecommendQuestion[];
}

const RecommendQuestions: React.FC<{
  initValue: any[];
  updateData: (data: RecommendQuestion[]) => void;
  classNames?: string;
  formStyle?: string;
  labelCol?: boolean;
}> = ({ initValue, updateData, classNames, formStyle, labelCol = true }) => {
  const [form] = Form.useForm<FormRecommendQuestion>();
  const recommendQuestions = Form.useWatch('recommend_questions', form);

  // 将数据实时返回给消费组件
  useEffect(() => {
    updateData(recommendQuestions?.filter((question) => !!question.question));
  }, [recommendQuestions, updateData]);

  return (
    <div className={cls(styles['recommend-questions-container'], classNames)}>
      <Form<FormRecommendQuestion>
        style={{ width: '100%' }}
        form={form}
        initialValues={{ recommend_questions: initValue || [{ question: '', valid: false }] }}
        autoComplete="off"
        wrapperCol={{ span: 21 }}
        {...(labelCol && { labelCol: { span: 3 } })}
      >
        <Form.Item label="推荐问题">
          <Form.List name="recommend_questions">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name }, index) => (
                  <div key={key} className={cls('flex flex-1 items-center gap-8 mb-6', formStyle)}>
                    <Form.Item label={`问题${index + 1}`} name={[name, 'question']} className="grow">
                      <Input placeholder="请输入推荐问题" />
                    </Form.Item>
                    <Form.Item label="是否生效" name={[name, 'valid']}>
                      <Switch style={{ background: recommendQuestions?.[index]?.valid ? '#1677ff' : '#ccc' }} />
                    </Form.Item>
                    <Form.Item>
                      <MinusCircleOutlined
                        onClick={() => {
                          remove(name);
                        }}
                      />
                    </Form.Item>
                  </div>
                ))}
                <Form.Item className={cls(formStyle)}>
                  <Button
                    type="dashed"
                    onClick={() => {
                      add({ question: '', valid: false });
                    }}
                    block
                    icon={<PlusOutlined />}
                  >
                    添加问题
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>
        </Form.Item>
      </Form>
    </div>
  );
};

export default RecommendQuestions;
