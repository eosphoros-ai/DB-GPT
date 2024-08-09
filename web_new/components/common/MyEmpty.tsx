import { Button, Empty } from 'antd';
import classNames from 'classnames';
import { useTranslation } from 'react-i18next';

interface Props {
  className?: string;
  error?: boolean;
  description?: string;
  refresh?: () => void;
}

function MyEmpty({ className, error, description, refresh }: Props) {
  const { t } = useTranslation();

  return (
    <Empty
      image="/empty.png"
      imageStyle={{ width: 320, height: 196, margin: '0 auto', maxWidth: '100%', maxHeight: '100%' }}
      className={classNames('flex items-center justify-center flex-col h-full w-full', className)}
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
