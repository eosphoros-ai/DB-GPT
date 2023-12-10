import React, { useState, useEffect } from 'react';
import { PlusOutlined } from '@ant-design/icons';
import { Button, Modal, Steps } from 'antd';
import SpaceCard from '@/components/knowledge/space-card';
import { ISpace, StepChangeParams } from '@/types/knowledge';
import { apiInterceptors, getSpaceList } from '@/client/api';
import { useTranslation } from 'react-i18next';
import DocUploadForm from '@/components/knowledge/doc-upload-form';
import SpaceForm from '@/components/knowledge/space-form';
import DocTypeForm from '@/components/knowledge/doc-type-form';

const Knowledge = () => {
  const [spaceList, setSpaceList] = useState<Array<ISpace> | null>([]);
  const [isAddShow, setIsAddShow] = useState<boolean>(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [spaceName, setSpaceName] = useState<string>('');
  const [docType, setDocType] = useState<string>('');
  const { t } = useTranslation();
  const addKnowledgeSteps = [{ title: t('Knowledge_Space_Config') }, { title: t('Choose_a_Datasource_type') }, { title: t('Setup_the_Datasource') }];

  async function getSpaces() {
    const [_, data] = await apiInterceptors(getSpaceList());
    setSpaceList(data);
  }
  useEffect(() => {
    getSpaces();
  }, []);

  const handleStepChange = ({ label, spaceName, docType }: StepChangeParams) => {
    if (label === 'finish') {
      setIsAddShow(false);
      getSpaces();
      setSpaceName('');
      setDocType('');
    } else if (label === 'forward') {
      activeStep === 0 && getSpaces();
      setActiveStep((step) => step + 1);
    } else {
      setActiveStep((step) => step - 1);
    }
    spaceName && setSpaceName(spaceName);
    docType && setDocType(docType);
  };

  function onAddDoc(spaceName: string) {
    setSpaceName(spaceName);
    setActiveStep(1);
    setIsAddShow(true);
  }

  return (
    <div className="bg-[#FAFAFA] dark:bg-[#212121] w-full h-full">
      <div className="page-body p-4 md:p-6 h-full overflow-auto">
        <Button
          type="primary"
          className="flex items-center"
          icon={<PlusOutlined />}
          onClick={() => {
            setIsAddShow(true);
          }}
        >
          Create
        </Button>
        <div className="flex flex-wrap mt-4">
          {spaceList?.map((space: ISpace) => (
            <SpaceCard key={space.id} space={space} onAddDoc={onAddDoc} getSpaces={getSpaces} />
          ))}
        </div>
      </div>
      <Modal
        title="Add Knowledge"
        centered
        open={isAddShow}
        destroyOnClose={true}
        onCancel={() => {
          setIsAddShow(false);
        }}
        width={1000}
        afterClose={() => {
          setActiveStep(0);
        }}
        footer={null}
      >
        <Steps current={activeStep} items={addKnowledgeSteps} />
        {activeStep === 0 && <SpaceForm handleStepChange={handleStepChange} />}
        {activeStep === 1 && <DocTypeForm handleStepChange={handleStepChange} />}
        {activeStep === 2 && <DocUploadForm spaceName={spaceName} docType={docType} handleStepChange={handleStepChange} />}
      </Modal>
    </div>
  );
};

export default Knowledge;
