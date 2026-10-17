import { apiInterceptors, getSpaceList } from '@/client/api';
import { ChatContentContext } from '@/pages/chat';
import { BookOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Select, Tooltip } from 'antd';
import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface ISpace {
  name: string;
  desc: string;
  id?: string;
}

const KnowledgeSelector: React.FC = () => {
  const { t } = useTranslation();
  const { knowledgeValue, setKnowledgeValue } = useContext(ChatContentContext);
  const [spaces, setSpaces] = useState<ISpace[]>([]);

  // Fetch knowledge spaces
  const { run: fetchSpaces, loading } = useRequest(async () => await apiInterceptors(getSpaceList()), {
    manual: true,
    onSuccess: data => {
      const [, res] = data;
      setSpaces(res || []);
    },
  });

  // Load spaces on mount
  useEffect(() => {
    fetchSpaces();
  }, []);

  const spaceOptions = useMemo(() => {
    return spaces.map(space => ({
      label: space.name,
      value: space.name,
      desc: space.desc,
    }));
  }, [spaces]);

  const handleChange = useCallback(
    (value: string) => {
      setKnowledgeValue(value || null);
    },
    [setKnowledgeValue],
  );

  return (
    <Tooltip title={t('select_knowledge_base')} arrow={false} placement='bottom'>
      <div className='flex items-center gap-2'>
        <Select
          value={knowledgeValue}
          onChange={handleChange}
          placeholder={
            <span className='flex items-center gap-1'>
              <BookOutlined />
              {t('knowledge')}
            </span>
          }
          allowClear
          loading={loading}
          options={spaceOptions}
          className='w-40 h-8'
          size='small'
          notFoundContent={t('no_knowledge_spaces')}
        />
      </div>
    </Tooltip>
  );
};

export default KnowledgeSelector;
