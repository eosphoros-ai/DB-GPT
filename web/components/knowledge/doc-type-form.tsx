import { StepChangeParams } from '@/types/knowledge';
import { Card } from 'antd';
import { useTranslation } from 'react-i18next';
import DocIcon from './doc-icon';

type IProps = {
  handleStepChange: (params: StepChangeParams) => void;
};

export default function DocTypeForm(props: IProps) {
  const { t } = useTranslation();
  const { handleStepChange } = props;
  const docTypeList = [
    {
      type: 'text',
      title: t('Text'),
      subTitle: t('Fill your raw text'),
      iconType: 'TEXT',
    },
    {
      type: 'webPage',
      title: t('URL'),
      subTitle: t('Fetch_the_content_of_a_URL'),
      iconType: 'WEBPAGE',
    },
    {
      type: 'file',
      title: t('Document'),
      subTitle: t('Upload_a_document'),
      iconType: 'DOCUMENT',
    },
  ];

  return (
    <>
      {docTypeList.map((type, index) => (
        <Card
          key={index}
          className="mt-4 mb-4 cursor-pointer"
          onClick={() => {
            handleStepChange({ label: 'forward', docType: type.type });
          }}
        >
          <div className="font-semibold">
            <DocIcon type={type.iconType} />
            {type.title}
          </div>
          <div>{type.subTitle}</div>
        </Card>
      ))}
    </>
  );
}
