import { DBOption, DBType } from '@/types/db';
import { Modal } from 'antd';
import { useTranslation } from 'react-i18next';
import DatabaseForm from './database-form';
import styles from './database.module.css';
import { useDatabaseCopy } from './presentation';

interface FormDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  dbTypeList: DBOption[];
  editValue?: string;
  choiceDBType?: DBType;
  initialParams?: Record<string, any>;
  description?: string;
}

export default function FormDialog(props: FormDialogProps) {
  const { i18n } = useTranslation();
  const { copy } = useDatabaseCopy(i18n.language);
  return (
    <Modal
      className={`${styles.modal} ${styles.surface}`}
      title={
        <div>
          {copy(
            props.editValue ? '编辑数据源' : '添加数据源',
            props.editValue ? 'Edit data source' : 'Add data source',
          )}
          <p className={styles.modalSubtitle}>
            {copy(
              '连接你的业务数据，为查询、分析和看板提供数据基础。',
              'Connect your data for queries, analysis and dashboards.',
            )}
          </p>
        </div>
      }
      open={props.open}
      onCancel={props.onClose}
      footer={null}
      width={640}
      destroyOnClose
      maskClosable={false}
      style={{ top: '6vh' }}
    >
      <DatabaseForm {...props} onCancel={props.onClose} />
    </Modal>
  );
}
