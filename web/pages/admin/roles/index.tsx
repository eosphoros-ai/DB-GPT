import { SafetyCertificateOutlined } from '@ant-design/icons';
import { App, Card, Empty, Spin, Tag } from 'antd';
import { useEffect, useState } from 'react';

import { listAdminRoles } from '@/client/api/admin';
import AdminLayout from '@/new-components/admin/AdminLayout';
import {
  AdminPageHeader,
  getAdminErrorMessage,
  requireAdminData,
  ROLE_COLORS,
  ROLE_LABELS,
} from '@/new-components/admin/AdminPage';
import { AdminRoleInfo } from '@/types/admin';

const ROLE_DESCRIPTIONS = {
  system_admin: '管理用户、角色、账套、授权、资源、用量和审计，拥有全局访问范围。',
  operations_admin: '在获授权账套内管理数据源、知识库和智能体，并查看相关用量。',
  query_user: '使用个人获授权的数据源、知识库和智能体，并查看本人用量。',
};

export default function AdminRolesPage() {
  const { message } = App.useApp();
  const [roles, setRoles] = useState<AdminRoleInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void listAdminRoles()
      .then(result => setRoles(requireAdminData(result)))
      .catch(error => message.error(getAdminErrorMessage(error, '角色信息加载失败')))
      .finally(() => setLoading(false));
  }, [message]);

  return (
    <AdminLayout>
      <AdminPageHeader title='角色权限' description='固定角色即权限组，本期不支持新增或自定义能力。' />
      {loading ? (
        <div className='py-20 text-center'>
          <Spin />
        </div>
      ) : roles.length === 0 ? (
        <Empty />
      ) : (
        <div className='grid grid-cols-1 gap-4 xl:grid-cols-3'>
          {roles.map(item => (
            <Card
              key={item.role}
              size='small'
              title={
                <span>
                  <SafetyCertificateOutlined className='mr-2' />
                  {ROLE_LABELS[item.role]}
                </span>
              }
              extra={<Tag color={ROLE_COLORS[item.role]}>{item.role}</Tag>}
            >
              <p className='mt-0 min-h-12 text-sm leading-6 text-gray-600'>{ROLE_DESCRIPTIONS[item.role]}</p>
              <div className='mb-3 text-sm text-gray-500'>
                关联用户：<strong className='text-gray-900'>{item.user_count}</strong>
              </div>
              <div className='flex flex-wrap gap-1.5'>
                {item.permissions.map(permission => (
                  <Tag className='m-0' key={permission}>
                    {permission}
                  </Tag>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </AdminLayout>
  );
}
