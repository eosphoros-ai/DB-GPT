import { Tooltip } from 'antd';
import { useTranslation } from 'react-i18next';

export default function UnviewedResultDot({ visible }: { visible: boolean }) {
  const { t } = useTranslation();
  if (!visible) return null;
  const label = t('conversation_completed_unviewed', '已完成，未查看');
  return (
    <Tooltip title={label}>
      <span role='status' aria-label={label} className='inline-flex h-5 w-5 shrink-0 items-center justify-center'>
        <span className='h-2 w-2 rounded-full bg-blue-500' />
      </span>
    </Tooltip>
  );
}
