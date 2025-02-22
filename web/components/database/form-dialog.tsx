import { ConfigurableParams } from '@/types/common';
import { DBOption, DBType } from '@/types/db';
import { Modal } from 'antd';
import { useTranslation } from 'react-i18next';
import DatabaseForm from './database-form';

interface NewFormDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  dbTypeList: DBOption[];
  editValue?: string;
  choiceDBType?: DBType;
  getFromRenderData?: ConfigurableParams[];
  dbNames?: string[];
  dbTypeData?: DBOption[];
  description?: string;
}

function FormDialog({
  open,
  onClose,
  onSuccess,
  dbTypeList,
  editValue,
  choiceDBType,
  getFromRenderData,
  dbNames,
  description,
}: NewFormDialogProps) {
  const { t } = useTranslation();

  return (
    <Modal
      title={t(editValue ? 'edit_database' : 'add_database')}
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      destroyOnClose
    >
      <DatabaseForm
        onCancel={onClose}
        onSuccess={onSuccess}
        dbTypeList={dbTypeList}
        editValue={editValue}
        choiceDBType={choiceDBType}
        getFromRenderData={getFromRenderData}
        dbNames={dbNames}
        description={description}
      />
    </Modal>
  );
}

export default FormDialog;
