import {
  ApartmentOutlined,
  AuditOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { Layout, Menu, Typography } from 'antd';
import { useRouter } from 'next/router';

import { AdminRole } from '@/types/admin';

interface AdminMenuItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  roles: AdminRole[];
}

const ALL_ROLES: AdminRole[] = ['system_admin', 'operations_admin', 'query_user'];

const ADMIN_MENU: AdminMenuItem[] = [
  { key: '/admin/users', label: '用户管理', icon: <UserOutlined />, roles: ['system_admin'] },
  { key: '/admin/roles', label: '角色权限', icon: <SafetyCertificateOutlined />, roles: ['system_admin'] },
  { key: '/admin/account-sets', label: '账套管理', icon: <ApartmentOutlined />, roles: ['system_admin'] },
  {
    key: '/admin/user-account-grants',
    label: '用户账套授权',
    icon: <TeamOutlined />,
    roles: ['system_admin'],
  },
  {
    key: '/admin/user-resource-grants',
    label: '用户资源授权',
    icon: <SafetyCertificateOutlined />,
    roles: ['system_admin'],
  },
  {
    key: '/admin/resources',
    label: '资源管理',
    icon: <DatabaseOutlined />,
    roles: ['system_admin', 'operations_admin'],
  },
  { key: '/admin/token-usage', label: 'Token 用量', icon: <BarChartOutlined />, roles: ALL_ROLES },
  { key: '/admin/audit', label: '审计日志', icon: <AuditOutlined />, roles: ['system_admin'] },
];

export const getDefaultAdminPath = (role: AdminRole) => {
  if (role === 'system_admin') return '/admin/users';
  if (role === 'operations_admin') return '/admin/resources';
  return '/admin/token-usage';
};

export const canAccessAdminPath = (role: AdminRole, path: string) => {
  const item = ADMIN_MENU.find(menuItem => path === menuItem.key || path.startsWith(`${menuItem.key}/`));
  return item ? item.roles.includes(role) : path === '/admin';
};

export function AdminSider({ role }: { role: AdminRole }) {
  const router = useRouter();
  const items: MenuProps['items'] = ADMIN_MENU.filter(item => item.roles.includes(role)).map(
    ({ roles: _roles, ...item }) => item,
  );
  const selected = ADMIN_MENU.find(item => router.pathname === item.key || router.pathname.startsWith(`${item.key}/`));

  return (
    <Layout.Sider
      breakpoint='lg'
      collapsedWidth={0}
      width={232}
      className='border-r border-solid border-gray-200 bg-white max-lg:absolute max-lg:inset-y-0 max-lg:left-0 max-lg:z-20 max-lg:shadow-lg'
      theme='light'
      zeroWidthTriggerStyle={{ top: 14 }}
    >
      <div className='flex h-16 items-center gap-3 border-0 border-b border-solid border-gray-200 px-5'>
        <img src='/LOGO_SMALL.png' width={30} height={30} alt='DB-GPT' />
        <div className='min-w-0'>
          <Typography.Text strong className='block text-[15px] leading-5'>
            DB-GPT
          </Typography.Text>
          <Typography.Text type='secondary' className='block text-xs leading-4'>
            管理后台
          </Typography.Text>
        </div>
      </div>
      <Menu
        className='border-0 px-2 py-3'
        items={items}
        mode='inline'
        selectedKeys={selected ? [selected.key] : []}
        onClick={({ key }) => void router.push(key)}
      />
    </Layout.Sider>
  );
}
