import { Spin } from 'antd';
import { useRouter } from 'next/router';
import { useEffect } from 'react';

import { getAdminCurrentUser } from '@/client/api/admin';
import { getDefaultAdminPath } from '@/new-components/admin/AdminSider';

export default function AdminIndexPage() {
  const router = useRouter();

  useEffect(() => {
    void getAdminCurrentUser()
      .then(result => {
        if (!result.success || !result.data) throw new Error('Not authenticated');
        return router.replace(getDefaultAdminPath(result.data.role));
      })
      .catch(() => router.replace('/admin/login'));
  }, [router]);

  return (
    <div className='flex h-screen w-screen items-center justify-center bg-gray-50' aria-label='正在进入管理后台'>
      <Spin size='large' />
    </div>
  );
}
