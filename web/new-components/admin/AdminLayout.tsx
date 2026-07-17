import { LogoutOutlined } from '@ant-design/icons';
import { App, Button, Layout, Spin, Tag, Typography } from 'antd';
import { useRouter } from 'next/router';
import { ReactNode, useEffect, useState } from 'react';

import { adminLogout } from '@/client/api/admin';
import { AdminAuthProvider, useAdminAuthGuard } from '@/hooks/use-admin-auth';
import { AdminRole } from '@/types/admin';

import { AdminSider, canAccessAdminPath, getDefaultAdminPath } from './AdminSider';

const ROLE_LABELS: Record<AdminRole, string> = {
  system_admin: '系统管理员',
  operations_admin: '运营管理员',
  query_user: '查询用户',
};

function AdminLayoutContent({ children }: { children: ReactNode }) {
  const { message } = App.useApp();
  const router = useRouter();
  const { user, loading } = useAdminAuthGuard();
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (user && !canAccessAdminPath(user.role, router.pathname)) {
      void router.replace(getDefaultAdminPath(user.role));
    }
  }, [router, user]);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      const result = await adminLogout();
      if (!result.success) throw new Error('Logout failed');
    } catch {
      message.error('退出登录失败，请重试');
      setLoggingOut(false);
      return;
    }
    await router.replace('/admin/login');
  };

  if (loading || !user) {
    return (
      <div className='flex h-screen w-screen items-center justify-center bg-gray-50' aria-label='正在验证登录状态'>
        <Spin size='large' />
      </div>
    );
  }

  return (
    <Layout className='h-screen min-h-[520px] bg-gray-50'>
      <AdminSider role={user.role} />
      <Layout className='min-w-0 overflow-hidden bg-gray-50'>
        <Layout.Header className='flex h-16 items-center justify-end gap-3 border-0 border-b border-solid border-gray-200 bg-white px-4 md:px-6'>
          <div className='min-w-0 text-right leading-5'>
            <Typography.Text className='block max-w-40 truncate text-sm' title={user.display_name}>
              {user.display_name}
            </Typography.Text>
            <Tag bordered={false} className='m-0 text-xs'>
              {ROLE_LABELS[user.role]}
            </Tag>
          </div>
          <Button
            aria-label='退出登录'
            icon={<LogoutOutlined />}
            loading={loggingOut}
            onClick={() => void handleLogout()}
            type='text'
          >
            <span className='hidden sm:inline'>退出</span>
          </Button>
        </Layout.Header>
        <Layout.Content className='min-h-0 overflow-auto p-4 md:p-6'>{children}</Layout.Content>
      </Layout>
    </Layout>
  );
}

export function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminAuthProvider>
      <AdminLayoutContent>{children}</AdminLayoutContent>
    </AdminAuthProvider>
  );
}

export default AdminLayout;
