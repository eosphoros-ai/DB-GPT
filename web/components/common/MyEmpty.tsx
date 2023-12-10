import { Button, Empty } from 'antd';
import { useTranslation } from 'react-i18next';

interface Props {
  error?: boolean;
  description?: string;
  refresh?: () => void;
}

function MyEmpty({ error, description, refresh }: Props) {
  const { t } = useTranslation();

  return (
    <Empty
      image="/empty.png"
      imageStyle={{ width: 320, height: 320, margin: '0 auto', maxWidth: '100%', maxHeight: '100%' }}
      className="flex items-center justify-center flex-col h-full w-full"
      description={
        error ? (
          <Button type="primary" onClick={refresh}>
            {t('try_again')}
          </Button>
        ) : (
          description ?? t('no_data')
        )
      }
    />
  );
}

export default MyEmpty;
