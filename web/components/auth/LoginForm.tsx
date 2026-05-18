import { apiInterceptors, login } from '@/client/api';
import { STORAGE_TOKEN_KEY, STORAGE_USERINFO_KEY, STORAGE_USERINFO_VALID_TIME_KEY } from '@/utils/constants/index';
import { Button, Form, Input, message } from 'antd';
import { useRouter } from 'next/router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export default function LoginForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const { t } = useTranslation();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const [err, data] = await apiInterceptors(login({ username: values.username, password: values.password }));
      if (err) {
        message.error(err.message || t('login_failed'));
        return;
      }
      if (data) {
        localStorage.setItem(STORAGE_TOKEN_KEY, data.token);
        localStorage.setItem(
          STORAGE_USERINFO_KEY,
          JSON.stringify({
            user_id: String(data.user_id),
            user_no: String(data.user_id),
            user_name: data.username,
            nick_name: data.real_name || data.username,
            real_name: data.real_name,
            role: data.user_role,
            user_group_id: data.user_group_id,
            user_group_name: data.user_group_name,
            phone: data.phone,
            email: data.email,
          }),
        );
        localStorage.setItem(STORAGE_USERINFO_VALID_TIME_KEY, Date.now().toString());
        message.success(t('login_success'));
        router.replace('/');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className='flex items-center justify-center min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800'>
      <div className='w-full max-w-md p-8 bg-white rounded-2xl shadow-lg dark:bg-gray-800'>
        <h1 className='text-2xl font-bold text-center mb-8 text-gray-800 dark:text-white'>{t('login_title')}</h1>
        <Form name='login' onFinish={onFinish} layout='vertical' size='large' autoComplete='off'>
          <Form.Item name='username' rules={[{ required: true, message: t('login_username_required') }]}>
            <Input placeholder={t('login_username_placeholder')} />
          </Form.Item>
          <Form.Item name='password' rules={[{ required: true, message: t('login_password_required') }]}>
            <Input.Password placeholder={t('login_password_placeholder')} />
          </Form.Item>
          <Form.Item>
            <Button type='primary' htmlType='submit' loading={loading} block className='h-10'>
              {t('login_btn')}
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
}
