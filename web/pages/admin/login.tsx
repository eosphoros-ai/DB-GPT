import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Button, Form, Input, Typography } from 'antd';
import type { AxiosError } from 'axios';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

import { adminLogin, getAdminCurrentUser } from '@/client/api/admin';
import { getDefaultAdminPath } from '@/new-components/admin/AdminSider';

interface LoginFormValues {
  loginName: string;
  password: string;
}

export default function AdminLoginPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void getAdminCurrentUser()
      .then(result => {
        if (active && result.success && result.data) {
          void router.replace(getDefaultAdminPath(result.data.role));
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [router]);

  const handleSubmit = async ({ loginName, password }: LoginFormValues) => {
    setSubmitting(true);
    setErrorMessage(null);
    try {
      const result = await adminLogin(loginName.trim(), password);
      if (!result.success || !result.data) throw new Error('Invalid authentication response');
      await router.replace(getDefaultAdminPath(result.data.user.role));
    } catch (error) {
      const status = (error as AxiosError).response?.status;
      setErrorMessage(status === 503 ? '认证服务暂不可用，请稍后重试' : '登录名或密码错误');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Head>
        <title>登录 | DB-GPT 管理后台</title>
        <meta name='viewport' content='width=device-width, initial-scale=1' />
      </Head>
      <main className='flex min-h-screen items-center justify-center bg-gray-100 px-4 py-8'>
        <section className='w-full max-w-[400px] rounded-md border border-solid border-gray-200 bg-white px-6 py-8 shadow-sm sm:px-8'>
          <div className='mb-7 flex items-center gap-3'>
            <img src='/LOGO_SMALL.png' width={42} height={42} alt='DB-GPT' />
            <div>
              <Typography.Title className='m-0 text-xl leading-7' level={1}>
                DB-GPT 管理后台
              </Typography.Title>
              <Typography.Text type='secondary' className='text-sm'>
                使用管理员账号登录
              </Typography.Text>
            </div>
          </div>

          {errorMessage && <Alert className='mb-5' message={errorMessage} type='error' showIcon />}

          <Form<LoginFormValues> layout='vertical' requiredMark={false} onFinish={values => void handleSubmit(values)}>
            <Form.Item
              label='登录名'
              name='loginName'
              rules={[{ required: true, whitespace: true, message: '请输入登录名' }]}
            >
              <Input
                autoComplete='username'
                prefix={<UserOutlined className='text-gray-400' />}
                placeholder='请输入登录名'
                size='large'
              />
            </Form.Item>
            <Form.Item label='密码' name='password' rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password
                autoComplete='current-password'
                prefix={<LockOutlined className='text-gray-400' />}
                placeholder='请输入密码'
                size='large'
              />
            </Form.Item>
            <Button className='mt-1 w-full' htmlType='submit' loading={submitting} size='large' type='primary'>
              登录
            </Button>
          </Form>
        </section>
      </main>
    </>
  );
}
