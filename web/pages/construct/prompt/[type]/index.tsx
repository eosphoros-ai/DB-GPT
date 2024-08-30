import { ChatContext } from '@/app/chat-context';
import {
  addPrompt,
  apiInterceptors,
  llmOutVerify,
  promptTemplateLoad,
  promptTypeTarget,
  updatePrompt,
} from '@/client/api';
import useUser from '@/hooks/use-user';
import ModelIcon from '@/new-components/chat/content/ModelIcon';
import { DebugParams, OperatePromptParams } from '@/types/prompt';
import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { LeftOutlined } from '@ant-design/icons';
import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import JsonView from '@uiw/react-json-view';
import { githubDarkTheme } from '@uiw/react-json-view/githubDark';
import { githubLightTheme } from '@uiw/react-json-view/githubLight';
import { useRequest } from 'ahooks';
import { Alert, App, Button, Card, Form, Input, InputNumber, Select, Slider, Space } from 'antd';
import classNames from 'classnames';
import MarkdownIt from 'markdown-it';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/router';
import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import 'react-markdown-editor-lite/lib/index.css';
import styles from '../styles.module.css';

const MarkdownEditor = dynamic(() => import('react-markdown-editor-lite'), {
  ssr: false,
});
const mdParser = new MarkdownIt();

const MarkdownContext = dynamic(() => import('@/new-components/common/MarkdownContext'), { ssr: false });

const TypeOptions = [
  {
    value: 'Agent',
    label: 'AGENT',
  },
  {
    value: 'Scene',
    label: 'SCENE',
  },
  {
    value: 'Normal',
    label: 'NORMAL',
  },
  {
    value: 'Evaluate',
    label: 'EVALUATE',
  },
];

interface BottomFormProps {
  model: string;
  temperature: number;
  prompt_language: 'en' | 'zh';
}

interface TopFormProps {
  prompt_type: string;
  prompt_name: string;
  target: string;
  prompt_code: string;
}

// 自定义温度选项
const TemperatureItem: React.FC<{
  value?: any;
  onChange?: (value: any) => void;
}> = ({ value, onChange }) => {
  // temperature变化;
  const onTemperatureChange = (value: any) => {
    if (isNaN(value)) {
      return;
    }
    onChange?.(value);
  };

  return (
    <div className='flex items-center gap-8'>
      <Slider className='w-40' min={0} max={1} step={0.1} onChange={onTemperatureChange} value={value} />
      <InputNumber className='w-16' min={0} max={1} step={0.1} value={value} onChange={onTemperatureChange} />
    </div>
  );
};

const AddOrEditPrompt: React.FC = () => {
  const router = useRouter();
  const { type = '' } = router.query;
  const { t } = useTranslation();

  const { modelList, model, mode } = useContext(ChatContext);
  const theme = mode === 'dark' ? githubDarkTheme : githubLightTheme;

  const { message } = App.useApp();

  const userInfo = useUser();

  // prompt内容
  const [value, setValue] = useState<string>('');
  // 输入参数
  const [variables, setVariables] = useState<string[]>([]);
  // 输出结构
  const [responseTemplate, setResponseTemplate] = useState<any>({});
  // LLM输出
  const [history, setHistory] = useState<Record<string, any>[]>([]);
  const [llmLoading, setLlmLoading] = useState<boolean>(false);

  // prompt基本信息
  const [topForm] = Form.useForm<TopFormProps>();
  // 输入参数
  const [midForm] = Form.useForm();
  // 模型，温度，语言
  const [bottomForm] = Form.useForm<BottomFormProps>();
  // 验证错误信息
  const [errorMessage, setErrorMessage] = useState<Record<string, any>>();

  const promptType = Form.useWatch('prompt_type', topForm);

  const modelOptions = useMemo(() => {
    return modelList.map(item => {
      return {
        value: item,
        label: (
          <div className='flex items-center'>
            <ModelIcon model={item} />
            <span className='ml-2'>{item}</span>
          </div>
        ),
      };
    });
  }, [modelList]);

  // md编辑器变化
  const onChange = useCallback((props: any) => {
    setValue(props.text);
  }, []);

  // 获取target选项
  const {
    data,
    run: getTargets,
    loading,
  } = useRequest(async (type: string) => await promptTypeTarget(type), {
    manual: true,
  });

  // 获取template
  const { run: getTemplate } = useRequest(
    async (target: string) =>
      await promptTemplateLoad({
        prompt_type: promptType,
        target: target ?? '',
      }),
    {
      manual: true,
      onSuccess: res => {
        if (res) {
          const { data } = res.data;
          setValue(data.template);
          setVariables(data.input_variables);
          try {
            const jsonTemplate = JSON.parse(data.response_format);
            setResponseTemplate(jsonTemplate || {});
          } catch {
            setResponseTemplate({});
          }
        }
      },
    },
  );

  // add or edit prompt
  const { run: operatePrompt, loading: operateLoading } = useRequest(
    async (params: OperatePromptParams) => {
      if (type === 'add') {
        return await apiInterceptors(addPrompt(params));
      } else {
        return await apiInterceptors(updatePrompt(params));
      }
    },
    {
      manual: true,
      onSuccess: () => {
        message.success(`${type === 'add' ? t('Add') : t('update')}${t('success')}`);
        router.replace('/construct/prompt');
      },
    },
  );

  const operateFn = () => {
    topForm.validateFields().then(async values => {
      const params: OperatePromptParams = {
        sub_chat_scene: '',
        model: bottomForm.getFieldValue('model'),
        chat_scene: values.target,
        prompt_name: values.prompt_name,
        prompt_type: values.prompt_type,
        content: value,
        response_schema: JSON.stringify(responseTemplate),
        input_variables: JSON.stringify(variables),
        prompt_language: bottomForm.getFieldValue('prompt_language'),
        prompt_desc: '',
        user_name: userInfo.nick_name,
        ...(type === 'edit' && { prompt_code: values.prompt_code }),
      };
      await operatePrompt(params);
    });
  };

  // llm测试
  const onLLMTest = async () => {
    if (llmLoading) {
      return;
    }
    const midVals = midForm.getFieldsValue();
    if (!Object.values(midVals).every(value => !!value)) {
      message.warning(t('Please_complete_the_input_parameters'));
      return;
    }
    if (!bottomForm.getFieldValue('user_input')) {
      message.warning(t('Please_fill_in_the_user_input'));
      return;
    }
    topForm.validateFields().then(async values => {
      const params: DebugParams = {
        sub_chat_scene: '',
        model: bottomForm.getFieldValue('model'),
        chat_scene: values.target,
        prompt_name: values.prompt_name,
        prompt_type: values.prompt_type,
        content: value,
        response_schema: JSON.stringify(responseTemplate),
        input_variables: JSON.stringify(variables),
        prompt_language: bottomForm.getFieldValue('prompt_language'),
        prompt_desc: '',
        prompt_code: values.prompt_code,
        temperature: bottomForm.getFieldValue('temperature'),
        debug_model: bottomForm.getFieldValue('model'),
        input_values: {
          ...midVals,
        },
        user_input: bottomForm.getFieldValue('user_input'),
      };
      const tempHistory: Record<string, any>[] = [{ role: 'view', context: '' }];
      const index = tempHistory.length - 1;
      try {
        setLlmLoading(true);
        await fetchEventSource(`${process.env.API_BASE_URL ?? ''}/prompt/template/debug`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            [HEADER_USER_ID_KEY]: getUserId() ?? '',
          },
          body: JSON.stringify(params),
          openWhenHidden: true,
          async onopen(response) {
            if (response.ok && response.headers.get('content-type') === EventStreamContentType) {
              return;
            }
          },
          onclose() {
            setLlmLoading(false);
          },
          onerror(err) {
            throw new Error(err);
          },
          onmessage: event => {
            let message = event.data;
            if (!message) return;
            try {
              message = JSON.parse(message).vis;
            } catch {
              message.replaceAll('\\n', '\n');
            }
            if (message === '[DONE]') {
              setLlmLoading(false);
            } else if (message?.startsWith('[ERROR]')) {
              setLlmLoading(false);
              tempHistory[index].context = message?.replace('[ERROR]', '');
            } else {
              tempHistory[index].context = message;
              setHistory([...tempHistory]);
            }
          },
        });
      } catch {
        setLlmLoading(false);
        tempHistory[index].context = 'Sorry, we meet some error, please try again later';
        setHistory([...tempHistory]);
      }
    });
  };

  // 输出验证
  const { run, loading: verifyLoading } = useRequest(
    async () =>
      await llmOutVerify({
        llm_out: history[0].context,
        prompt_type: topForm.getFieldValue('prompt_type'),
        chat_scene: topForm.getFieldValue('target'),
      }),
    {
      manual: true,
      onSuccess: res => {
        if (res?.data?.success) {
          setErrorMessage({ msg: '验证通过', status: 'success' });
        } else {
          setErrorMessage({ msg: res?.data?.err_msg, status: 'error' });
        }
      },
    },
  );

  // 设置默认模型
  useEffect(() => {
    if (model) {
      bottomForm.setFieldsValue({
        model,
      });
    }
  }, [bottomForm, model]);

  // 类型改变获取相应的场景
  useEffect(() => {
    if (promptType) {
      getTargets(promptType);
    }
  }, [getTargets, promptType]);

  const targetOptions = useMemo(() => {
    return data?.data?.data?.map((option: any) => {
      return {
        ...option,
        value: option.name,
        label: option.name,
      };
    });
  }, [data]);

  // 编辑进入填充内容
  useEffect(() => {
    if (type === 'edit') {
      const editData = JSON.parse(localStorage.getItem('edit_prompt_data') || '{}');
      setVariables(JSON.parse(editData.input_variables ?? '[]'));
      setValue(editData?.content);
      topForm.setFieldsValue({
        prompt_type: editData.prompt_type,
        prompt_name: editData.prompt_name,
        prompt_code: editData.prompt_code,
        target: editData.chat_scene,
      });
      bottomForm.setFieldsValue({
        model: editData.model,
        prompt_language: editData.prompt_language,
      });
    }
  }, [bottomForm, topForm, type]);

  return (
    <div
      className={`flex flex-col w-full h-full justify-between dark:bg-gradient-dark ${styles['prompt-operate-container']}`}
    >
      <header className='flex items-center justify-between px-6 py-2 h-14 border-b border-[#edeeef]'>
        <Space className='flex items-center'>
          <LeftOutlined
            className='text-base cursor-pointer hover:text-[#0c75fc]'
            onClick={() => {
              localStorage.removeItem('edit_prompt_data');
              router.replace('/construct/prompt');
            }}
          />
          <span className='font-medium text-sm'>{type === 'add' ? t('Add') : t('Edit')} Prompt</span>
        </Space>
        <Space>
          <Button type='primary' onClick={operateFn} loading={operateLoading}>
            {type === 'add' ? t('save') : t('update')}
          </Button>
        </Space>
      </header>
      <section className='flex h-full p-4 gap-4'>
        {/* 编辑展示区 */}
        <div className='flex flex-col flex-1 h-full overflow-y-auto pb-8 '>
          <MarkdownEditor
            value={value}
            onChange={onChange}
            renderHTML={text => mdParser.render(text)}
            view={{ html: false, md: true, menu: true }}
          />
          {/* llm 输出区域 */}
          {history.length > 0 && (
            <Card
              title={
                <Space>
                  <span>LLM OUT</span>
                  {errorMessage && <Alert message={errorMessage.msg} type={errorMessage.status} showIcon />}
                </Space>
              }
              className='mt-2'
            >
              <div className=' max-h-[400px] overflow-y-auto'>
                <MarkdownContext>{history?.[0]?.context.replace(/\\n/gm, '\n')}</MarkdownContext>
              </div>
            </Card>
          )}
        </div>
        {/* 功能区 */}
        <div className='flex flex-col w-2/5 pb-8 overflow-y-auto'>
          <Card className='mb-4'>
            <Form form={topForm}>
              <div className='flex w-full gap-1 justify-between'>
                <Form.Item
                  label='Type'
                  name='prompt_type'
                  className='w-2/5'
                  rules={[{ required: true, message: t('select_type') }]}
                >
                  <Select options={TypeOptions} placeholder={t('select_type')} allowClear />
                </Form.Item>
                <Form.Item name='target' className='w-3/5' rules={[{ required: true, message: t('select_scene') }]}>
                  <Select
                    loading={loading}
                    placeholder={t('select_scene')}
                    allowClear
                    showSearch
                    onChange={async value => {
                      await getTemplate(value);
                    }}
                  >
                    {targetOptions?.map(option => (
                      <Select.Option key={option.value} title={option.desc}>
                        {option.label}
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>
              </div>
              {type === 'edit' && (
                <Form.Item label='Code' name='prompt_code'>
                  <Input disabled />
                </Form.Item>
              )}
              <Form.Item
                label='Name'
                name='prompt_name'
                className='m-0'
                rules={[{ required: true, message: t('Please_input_prompt_name') }]}
              >
                <Input placeholder={t('Please_input_prompt_name')} />
              </Form.Item>
            </Form>
          </Card>
          <Card title={t('input_parameter')} className='mb-4'>
            <Form form={midForm}>
              {variables.length > 0 &&
                variables
                  .filter(item => item !== 'out_schema')
                  .map(item => (
                    <Form.Item key={item} label={item} name={item} rules={[{ message: `${t('Please_Input')}${item}` }]}>
                      <Input placeholder={t('Please_Input')} />
                    </Form.Item>
                  ))}
            </Form>
          </Card>
          <Card title={t('output_structure')} className='flex flex-col flex-1'>
            <JsonView
              style={{ ...theme, width: '100%', padding: 4 }}
              className={classNames({
                'bg-[#fafafa]': mode === 'light',
              })}
              value={responseTemplate}
              enableClipboard={false}
              displayDataTypes={false}
              objectSortKeys={false}
            />
            <div className='flex flex-col mt-4'>
              <Form
                form={bottomForm}
                initialValues={{
                  model: model,
                  temperature: 0.5,
                  prompt_language: 'en',
                }}
              >
                <Form.Item label={t('model')} name='model'>
                  <Select className='h-8 rounded-3xl' options={modelOptions} allowClear showSearch />
                </Form.Item>
                <Form.Item label={t('temperature')} name='temperature'>
                  <TemperatureItem />
                </Form.Item>
                <Form.Item label={t('language')} name='prompt_language'>
                  <Select
                    options={[
                      {
                        label: t('English'),
                        value: 'en',
                      },
                      {
                        label: t('Chinese'),
                        value: 'zh',
                      },
                    ]}
                  />
                </Form.Item>
                <Form.Item label={t('User_input')} name='user_input'>
                  <Input placeholder={t('Please_Input')} />
                </Form.Item>
              </Form>
            </div>
            <Space className='flex justify-between'>
              <Button type='primary' onClick={onLLMTest} loading={llmLoading}>
                {t('LLM_test')}
              </Button>
              <Button
                type='primary'
                onClick={async () => {
                  if (verifyLoading || !history[0]?.context) {
                    return;
                  }
                  await run();
                }}
              >
                {t('Output_verification')}
              </Button>
            </Space>
          </Card>
        </div>
      </section>
    </div>
  );
};

export default AddOrEditPrompt;

export async function getStaticProps({ params }: { params: { type: string } }) {
  const { type } = params;
  // 根据动态路由参数 scene 获取所需的数据

  return {
    props: {
      type,
    },
  };
}

export async function getStaticPaths() {
  // 返回可能的动态路由参数为空，表示所有的页面都将在访问时生成
  return {
    paths: [{ params: { type: 'add' } }, { params: { type: 'edit' } }],
    fallback: 'blocking',
  };
}
