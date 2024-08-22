import AppDefaultIcon from '@/new-components/common/AppDefaultIcon';
import { CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { Spin, Tooltip, Typography } from 'antd';
import React, { useMemo } from 'react';

interface VisAppLinkProps {
  status: string;
  app_name: string;
  app_desc: string;
  msg: string;
}

const VisAppLink: React.FC<{ data: VisAppLinkProps }> = ({ data }) => {
  const statusRender = useMemo(() => {
    switch (data.status) {
      case 'todo':
        return <ClockCircleOutlined />;
      case 'failed':
        return <CloseCircleOutlined className="text-[rgb(255,77,79)]" />;
      case 'complete':
        return <CheckCircleOutlined className="text-[rgb(82,196,26)]" />;
      case 'running':
        return <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />;
      default:
        return null;
    }
  }, [data]);
  if (!data) return null;
  return (
    <div className="flex flex-col p-2 border pr-4 rounded-md min-w-fit w-2/5">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <AppDefaultIcon scene={'chat_agent'} width={8} height={8} />
          <div className="flex flex-col flex-1 ml-2">
            <div className="flex items-center text-sm dark:text-[rgba(255,255,255,0.85)] gap-2">{data?.app_name}</div>
            <Typography.Text
              className="text-sm text-[#525964] dark:text-[rgba(255,255,255,0.65)] leading-6"
              ellipsis={{
                tooltip: true,
              }}
            >
              {data?.app_desc}
            </Typography.Text>
          </div>
        </div>
        <div className="text-2xl ml-1">{statusRender}</div>
      </div>
      {data.status === 'failed' && data.msg && (
        <Typography.Text type="danger" className="pl-12 text-xs mt-2">
          {data.msg}
        </Typography.Text>
      )}
    </div>
  );
};

export default VisAppLink;
