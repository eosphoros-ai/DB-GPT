import { apiInterceptors, getAppStrategyValues } from '@/client/api';
import MarkDownContext from '@/new-components/common/MarkdownContext';
import { IResource } from '@/types/app';
import { ExclamationCircleOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Form, Modal, Select } from 'antd';
import cls from 'classnames';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { v4 as uuid } from 'uuid';
import ResourcesCard from './ResourcesCard';

type PromptSelectType = {
  promptList: Record<string, any>[];
  value?: string;
  onChange?: (value: string) => void;
};
// 自定义prompt控件
const PromptSelect: React.FC<PromptSelectType> = ({ value, onChange, promptList }) => {
  const [showPrompt, setShowPrompt] = useState<boolean>(false);
  const [curPrompt, setCurPrompt] = useState<Record<string, any>>();
  const { t } = useTranslation();
  useEffect(() => {
    if (value) {
      const filterPrompt = promptList?.filter(item => item.prompt_code === value)[0];
      setCurPrompt(filterPrompt);
    }
  }, [promptList, value]);

  return (
    <div className='w-2/5 flex items-center gap-2'>
      <Select
        className='w-1/2'
        placeholder={t('please_select_prompt')}
        options={promptList}
        fieldNames={{ label: 'prompt_name', value: 'prompt_code' }}
        onChange={value => {
          const filterPrompt = promptList?.filter(item => item.prompt_code === value)[0];
          setCurPrompt(filterPrompt);
          onChange?.(value);
        }}
        value={value}
        allowClear
        showSearch
      />
      {curPrompt && (
        <span className='text-sm text-blue-500 cursor-pointer' onClick={() => setShowPrompt(true)}>
          <ExclamationCircleOutlined className='mr-1' />
          {t('View_details')}
        </span>
      )}
      <Modal
        title={`Prompt ${t('details')}`}
        open={showPrompt}
        footer={false}
        width={'60%'}
        onCancel={() => setShowPrompt(false)}
      >
        <MarkDownContext>{curPrompt?.content}</MarkDownContext>
      </Modal>
    </div>
  );
};

const DetailsCard: React.FC<{
  name: string;
  initValue: any;
  modelStrategyOptions: any[];
  resourceTypeOptions: Record<string, any>[];
  updateData: (data: any) => void;
  classNames?: string;
  promptList: Record<string, any>[];
}> = ({ name, initValue, modelStrategyOptions, resourceTypeOptions, updateData, classNames, promptList }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const promptTemplate = Form.useWatch('prompt_template', form);
  const strategy = Form.useWatch('llm_strategy', form);
  const strategyValue = Form.useWatch('llm_strategy_value', form);

  // const [curPrompt, setCurPrompt] = useState<Record<string, any>>();
  // const [showPrompt, setShowPrompt] = useState<boolean>(false);

  const initVal = useMemo(() => {
    return initValue?.find((item: any) => item.agent_name === name) || [];
  }, [initValue, name]);

  const resourcesRef = useRef<IResource[]>([]);

  // 获取模型策略参数列表
  const { run, loading, data } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(getAppStrategyValues('priority'));
      return (
        res?.map(item => {
          return {
            label: item,
            value: item,
          };
        }) ?? []
      );
    },
    {
      manual: true,
    },
  );

  // 选择模型策略为priority获取参数
  useEffect(() => {
    if (strategy === 'priority') {
      run();
    }
  }, [run, strategy]);

  // 数据实时返回消费组件
  useEffect(() => {
    const rawVal = form.getFieldsValue();
    updateData({
      agent_name: name,
      ...rawVal,
      llm_strategy_value: rawVal?.llm_strategy_value?.join(','),
      resources: resourcesRef.current,
    });
  }, [form, loading, name, promptTemplate, strategy, strategyValue, updateData]);

  return (
    <div className={cls(classNames)}>
      <Form
        style={{ width: '100%' }}
        labelCol={{ span: 4 }}
        form={form}
        initialValues={{
          llm_strategy: 'default',
          ...initVal,
          llm_strategy_value: initVal?.llm_strategy_value?.split(','),
        }}
      >
        <Form.Item label={t('Prompt')} name='prompt_template'>
          <PromptSelect promptList={promptList} />
        </Form.Item>
        <Form.Item label={t('LLM_strategy')} required name='llm_strategy'>
          <Select
            className='w-1/5'
            placeholder={t('please_select_LLM_strategy')}
            options={modelStrategyOptions}
            allowClear
          />
        </Form.Item>
        {strategy === 'priority' && (
          <Form.Item label={t('LLM_strategy_value')} required name='llm_strategy_value'>
            <Select
              mode='multiple'
              className='w-2/5'
              placeholder={t('please_select_LLM_strategy_value')}
              options={data}
              allowClear
            />
          </Form.Item>
        )}
        <Form.Item label={t('available_resources')} name='resources'>
          <ResourcesCard
            resourceTypeOptions={resourceTypeOptions}
            initValue={initVal?.resources?.map((res: any) => {
              return {
                ...res,
                uid: uuid(),
              };
            })}
            updateData={data => {
              resourcesRef.current = data?.[1];
              updateData({
                agent_name: name,
                resources: resourcesRef.current,
              });
            }}
            name={name}
          />
        </Form.Item>
      </Form>
    </div>
  );
};

export default DetailsCard;
