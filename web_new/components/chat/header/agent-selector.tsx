import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getDbgptsList } from '@/client/api';
import { useRequest } from 'ahooks';
import { Select } from 'antd';
import { useContext } from 'react';
import { useTranslation } from 'react-i18next';

function AgentSelector() {
  const { t } = useTranslation();
  const { agent, setAgent } = useContext(ChatContext);

  const { data = [] } = useRequest(async () => {
    const [, res] = await apiInterceptors(getDbgptsList());
    return res ?? [];
  });

  return (
    <Select
      className="w-60"
      value={agent}
      placeholder={t('Select_Plugins')}
      options={data.map((item) => ({ label: item.app_name, value: item.app_code }))}
      allowClear
      onChange={(val) => {
        setAgent?.(val);
      }}
    />
  );
}

export default AgentSelector;
