import { apiInterceptors, updateApp } from '@/client/api';
import AppDefaultIcon from '@/new-components/common/AppDefaultIcon';
import { CreateAppParams } from '@/types/app';
import { EditOutlined, LeftOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { App, Button, Space, Spin } from 'antd';
import classNames from 'classnames';
import _ from 'lodash';
import { useRouter } from 'next/router';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import CreateAppModal from '../components/create-app-modal';
import AwelLayout from './components/AwelLayout';
import NativeApp from './components/NativeApp';
import RecommendQuestions from './components/RecommendQuestions';
import AutoPlan from './components/auto-plan';
import styles from './styles.module.css';

const ExtraAppInfo: React.FC = () => {
  // 获取当前应用信息
  const curApp = JSON.parse(localStorage.getItem('new_app_info') || '{}');
  const { t } = useTranslation();
  const { message } = App.useApp();
  const router = useRouter();

  const [loading, setLoading] = useState<boolean>(false);
  const [open, setOpen] = useState<boolean>(false);
  const [dataReady, setDataReady] = useState<boolean>(false);
  const appParams = useRef<CreateAppParams>({});
  const initialParams = useRef<CreateAppParams>({});

  // 初始化参数，保留原有资源
  useEffect(() => {
    try {
      // 深度克隆当前应用数据到初始参数和当前参数
      initialParams.current = {
        app_code: curApp?.app_code,
        app_describe: curApp?.app_describe,
        team_mode: curApp?.team_mode,
        app_name: curApp?.app_name,
        language: curApp?.language,
        details: _.cloneDeep(curApp?.details || []),
        team_context: _.cloneDeep(curApp?.team_context || {}),
        param_need: _.cloneDeep(curApp?.param_need || []),
        recommend_questions: _.cloneDeep(curApp?.recommend_questions || []),
      };

      // 复制一份给当前操作的参数
      appParams.current = _.cloneDeep(initialParams.current);

      setDataReady(true);
    } catch (_) {
      message.error(t('Update_failure'));
    }
  }, [curApp, message, t]);

  // 更新应用
  const { run: update, loading: createLoading } = useRequest(
    async (params: CreateAppParams) => {
      try {
        return await apiInterceptors(
          updateApp({
            app_code: curApp?.app_code,
            app_describe: curApp?.app_describe,
            team_mode: curApp?.team_mode,
            app_name: curApp?.app_name,
            language: curApp?.language,
            ...params,
          }),
        );
      } catch (error) {
        message.error(t('update_failed'));
        throw error;
      }
    },
    {
      manual: true,
      onSuccess: data => {
        const [, res] = data;
        if (res) {
          message.success(t('update_success'));
          router.replace('/construct/app');
        } else {
          message.error(t('update_failed'));
        }
      },
      onError: _ => {
        message.error(t('update_failed'));
      },
    },
  );

  // 更新子组件改变的数据到appParams
  const updateComponentData = (key: keyof CreateAppParams, value: any) => {
    if (!appParams.current) return;

    try {
      // 使用深拷贝避免引用问题
      appParams.current[key] = _.cloneDeep(value);
    } catch (_) {
      // 错误处理
    }
  };

  const submit = async () => {
    if (!dataReady) {
      message.warning('Please wait, data is loading');
      return;
    }

    if (loading) {
      message.warning('Please wait, data is loading');
      return;
    }

    try {
      // 确保必要的字段存在
      const finalParams: CreateAppParams = {};

      // 添加基本信息
      finalParams.app_code = curApp?.app_code;
      finalParams.app_name = curApp?.app_name;
      finalParams.app_describe = curApp?.app_describe;
      finalParams.team_mode = curApp?.team_mode;
      finalParams.language = curApp?.language;

      // 根据模式添加相应数据
      if (['single_agent', 'auto_plan'].includes(curApp?.team_mode)) {
        finalParams.details = appParams.current.details || initialParams.current.details;
      }

      if (curApp?.team_mode === 'awel_layout') {
        finalParams.team_context = appParams.current.team_context || initialParams.current.team_context;
      }

      if (curApp?.team_mode === 'native_app') {
        finalParams.team_context = appParams.current.team_context || initialParams.current.team_context;
        finalParams.param_need = appParams.current.param_need || initialParams.current.param_need;
      }

      finalParams.recommend_questions =
        appParams.current.recommend_questions || initialParams.current.recommend_questions;

      await update(finalParams);
    } catch (_) {
      message.error(t('update_failed'));
    }
  };

  const recommendQuestionsStyle = useMemo(() => {
    if (curApp?.team_mode === 'awel_layout') {
      return 'px-6';
    }
    if (curApp?.team_mode === 'auto_plan') {
      return 'w-3/4 mx-auto';
    }
    return 'w-3/5 mx-auto';
  }, [curApp?.team_mode]);

  return (
    <App>
      <Spin spinning={loading}>
        <div
          className={classNames(
            'flex flex-col  h-screen w-screen dark:bg-gradient-dark bg-gradient-light bg-cover bg-center',
            styles['extra-container'],
          )}
        >
          <header className='flex items-center justify-between px-6 py-2 h-14 border-b border-[#edeeef]'>
            <Space className='flex items-center'>
              <LeftOutlined
                className='text-base cursor-pointer hover:text-[#0c75fc]'
                onClick={() => {
                  router.replace('/construct/app');
                }}
              />
              <div className='flex items-center justify-center w-10 h-10 border border-[#d6d8da] rounded-lg'>
                <AppDefaultIcon scene={curApp?.team_context?.chat_scene || 'chat_agent'} />
              </div>
              <span>{curApp?.app_name}</span>
              <EditOutlined className='cursor-pointer hover:text-[#0c75fc]' onClick={() => setOpen(true)} />
            </Space>
            <Button type='primary' onClick={submit} loading={createLoading} disabled={loading}>
              {curApp?.isEdit ? t('update') : t('save')}
            </Button>
          </header>
          <div className='flex flex-1 flex-col py-12 max-h-full overflow-y-auto'>
            {/* auto_plan模式 */}
            {['single_agent', 'auto_plan'].includes(curApp?.team_mode) && (
              <AutoPlan
                classNames='w-3/4 mx-auto'
                updateData={data => {
                  setLoading(data?.[0]);
                  if (data?.[1]) {
                    updateComponentData('details', data[1]);
                  }
                }}
                initValue={curApp?.details}
              />
            )}
            {/* awel_layout模式 */}
            {curApp?.team_mode === 'awel_layout' && (
              <AwelLayout
                initValue={curApp?.team_context}
                updateData={data => {
                  setLoading(data?.[0]);
                  if (data?.[1]) {
                    updateComponentData('team_context', data[1]);
                  }
                }}
                classNames='px-6'
              />
            )}
            {/* native_app模式 */}
            {curApp?.team_mode === 'native_app' && (
              <NativeApp
                initValue={{
                  team_context: curApp?.team_context,
                  param_need: curApp?.param_need,
                }}
                classNames='w-3/5 mx-auto'
                updateData={(data: any) => {
                  setLoading(data?.[0]);
                  if (data?.[1]) {
                    updateComponentData('team_context', data?.[1]?.[0]);
                    updateComponentData('param_need', data?.[1]?.[1]);
                  }
                }}
              />
            )}
            {/* single_agent模式 */}
            {/* {curApp?.team_mode === '' && <></>} */}
            <RecommendQuestions
              updateData={data => {
                if (data) {
                  updateComponentData('recommend_questions', data);
                }
              }}
              classNames={recommendQuestionsStyle}
              initValue={curApp?.recommend_questions}
              labelCol={curApp?.team_mode !== 'awel_layout'}
            />
          </div>
        </div>
      </Spin>
      <CreateAppModal type='edit' open={open} onCancel={() => setOpen(false)} />
    </App>
  );
};

export default ExtraAppInfo;
