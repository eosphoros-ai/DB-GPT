import {
  ColorfulChat,
  ColorfulDB,
  ColorfulDashboard,
  ColorfulData,
  ColorfulDoc,
  ColorfulExcel,
  ColorfulPlugin,
} from '@/components/icons';
import Icon from '@ant-design/icons';
import React, { useCallback } from 'react';

const AppDefaultIcon: React.FC<{ scene: string; width?: number; height?: number }> = ({ width, height, scene }) => {
  const returnComponent = useCallback(() => {
    switch (scene) {
      case 'chat_knowledge':
        return ColorfulDoc;
      case 'chat_with_db_execute':
        return ColorfulData;
      case 'chat_excel':
        return ColorfulExcel;
      case 'chat_with_db_qa':
      case 'chat_dba':
        return ColorfulDB;
      case 'chat_dashboard':
        return ColorfulDashboard;
      case 'chat_agent':
        return ColorfulPlugin;
      case 'chat_normal':
        return ColorfulChat;
      default:
        return;
    }
  }, [scene]);

  return <Icon className={`w-${width || 7} h-${height || 7}`} component={returnComponent()} />;
};

export default AppDefaultIcon;
