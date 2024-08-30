import { apiInterceptors, getAppStrategyValues, getNativeAppScenes, getResource } from '@/client/api';
import AppDefaultIcon from '@/new-components/common/AppDefaultIcon';
import { ParamNeed } from '@/types/app';
import { useRequest } from 'ahooks';
import { Form, InputNumber, Select, Tooltip } from 'antd';
import cls from 'classnames';
import React, { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

interface TeamContext {
  scene_name?: string;
  chat_scene?: string;
}
interface InitValueProps {
  team_context: TeamContext;
  param_need: ParamNeed[];
}

interface FormProps {
  chat_scene?: string;
  bind_value?: string;
  model?: string;
  temperature?: number;
}

const NativeApp: React.FC<{
  updateData: (data: [boolean, [TeamContext, ParamNeed[]]]) => void;
  classNames?: string;
  initValue?: InitValueProps;
}> = ({ classNames, initValue, updateData }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm<FormProps>();
  const chatScene = Form.useWatch('chat_scene', form);
  const bindValue = Form.useWatch('bind_value', form);
  const model = Form.useWatch('model', form);
  const temperature = Form.useWatch('temperature', form);

  const { team_context, param_need } = initValue || {};

  // 获取应用类型&模型
  const { data, loading } = useRequest(async () => {
    const res = await Promise.all([
      apiInterceptors(getNativeAppScenes()),
      apiInterceptors(getAppStrategyValues('priority')),
    ]);
    const [types, models] = res;
    form.setFieldValue('chat_scene', team_context?.chat_scene);
    form.setFieldValue('model', param_need?.find(param => param.type === 'model')?.value);
    form.setFieldValue('temperature', param_need?.find(param => param.type === 'temperature')?.value);
    await run(param_need?.find(param => param.type === 'resource')?.value || '');
    return [types, models] ?? [];
  });

  // 获取资源类型参数列表
  const {
    data: options,
    loading: paramsLoading,
    run,
  } = useRequest(
    async (type: string) => {
      const [, res] = await apiInterceptors(getResource({ type }));
      if (chatScene === team_context?.chat_scene && param_need?.find(param => param.type === 'resource')?.bind_value) {
        form.setFieldsValue({
          bind_value: param_need?.find(param => param.type === 'resource')?.bind_value,
        });
      }

      return (
        res?.map(item => {
          return {
            ...item,
            value: item.key,
          };
        }) ?? []
      );
    },
    { manual: true },
  );

  // 应用类型选项
  const appTypeOptions = useMemo(() => {
    const types = data?.[0]?.[1];
    return (
      types?.map((type: any) => {
        return {
          ...type,
          label: (
            <div className='flex items-center gap-1'>
              <AppDefaultIcon width={4} height={4} scene={type.chat_scene} />
              <Tooltip title={`资源类型${type.param_need.find((param: any) => param.type === 'resource')?.value}`}>
                <span className='text-[#525964] dark:text-[rgba(255,255,255,0.65)]  ml-1'>{type.scene_name}</span>
              </Tooltip>
            </div>
          ),
          value: type.chat_scene,
        };
      }) || []
    );
  }, [data]);

  // 将数据实时返回给消费组件
  useEffect(() => {
    const rawVal = form.getFieldsValue();

    updateData([
      loading,
      [
        {
          chat_scene: rawVal.chat_scene,
          scene_name: appTypeOptions.find(type => type.chat_scene === rawVal.chat_scene)?.scene_name,
        },
        [
          { type: 'model', value: rawVal.model },
          { type: 'temperature', value: rawVal.temperature },
          {
            type: 'resource',
            value: appTypeOptions
              .find(type => type.chat_scene === rawVal.chat_scene)
              ?.param_need?.find((param: any) => param.type === 'resource')?.value,
            bind_value: rawVal.bind_value,
          },
        ],
      ],
    ]);
  }, [form, chatScene, bindValue, model, temperature, updateData, appTypeOptions, loading]);

  useEffect(() => {
    const type = (data?.[0]?.[1]?.find((type: any) => type.chat_scene === chatScene) as any)?.param_need?.find(
      (param: any) => param.type === 'resource',
    )?.value;
    run(type || '');
  }, [chatScene, data, run]);

  return (
    <div className={cls(classNames)}>
      <Form<FormProps>
        form={form}
        autoComplete='off'
        style={{ width: '100%' }}
        labelCol={{ span: 3 }}
        wrapperCol={{ span: 21 }}
      >
        <Form.Item label={t('native_type')} tooltip name='chat_scene'>
          <Select
            className='w-1/2'
            options={appTypeOptions}
            placeholder={t('app_type_select')}
            onChange={() => form.setFieldsValue({ bind_value: undefined })}
          />
        </Form.Item>
        {chatScene !== 'chat_excel' && (
          <Form.Item label={t('Arguments')} name='bind_value'>
            <Select
              placeholder={t('please_select_param')}
              allowClear
              className='w-1/2'
              options={options}
              loading={paramsLoading}
            />
          </Form.Item>
        )}
        <Form.Item label={t('model')} tooltip name='model'>
          <Select
            placeholder={t('please_select_model')}
            allowClear
            options={data?.[1]?.[1]?.map(item => ({
              label: item,
              value: item,
            }))}
            className='w-1/2'
          />
        </Form.Item>
        <Form.Item label={t('temperature')} tooltip name='temperature'>
          <InputNumber className='w-1/5 h-8' max={1} min={0} step={0.1} placeholder={t('please_input_temperature')} />
        </Form.Item>
      </Form>
    </div>
  );
};

export default NativeApp;
