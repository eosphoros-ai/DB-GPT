import i18n from '@/app/i18n';
import { ChatContentContext } from '@/pages/chat';
import { MobileChatContext } from '@/pages/mobile/chat';
import { Button } from 'antd';
import React, { useContext } from 'react';
import { useTranslation } from 'react-i18next';

interface VisChatLinkProps {
  children: any;
  msg: string;
}
const VisChatLink: React.FC<VisChatLinkProps> = ({ children, msg }) => {
  const { handleChat: webHandleChat } = useContext(ChatContentContext);
  const { handleChat: mobileHandleChat } = useContext(MobileChatContext);
  return (
    <Button
      className='ml-1 inline text-xs'
      onClick={() => {
        mobileHandleChat?.(msg);
        webHandleChat?.(msg);
      }}
      type='dashed'
      size='small'
    >
      {children || i18n.t('click_to_analyze_current_anomaly')}
    </Button>
  );
};

export default VisChatLink;
