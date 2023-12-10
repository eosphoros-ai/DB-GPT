import { useState, useEffect, useRef, Ref } from 'react';
import type { ColumnsType } from 'antd/es/table';
import type { FormInstance, MenuProps } from 'antd';
import { Menu, Table, Button, Tooltip, Modal } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import GroupsIcon from '@mui/icons-material/Groups';
import PersonIcon from '@mui/icons-material/Person';
import { useTranslation } from 'react-i18next';
import { addPrompt, apiInterceptors, getPromptList, postScenes, updatePrompt } from '@/client/api';
import { IPrompt } from '@/types/prompt';
import PromptForm from '@/components/prompt/prompt-form';
import { TFunction } from 'i18next';

const getItems = (t: TFunction) => [
  {
    label: t('Public') + ' Prompts',
    key: 'common',
    icon: <GroupsIcon />,
  },
  {
    label: t('Private') + ' Prompts',
    key: 'private',
    icon: <PersonIcon />,
  },
];

const getColumns = (t: TFunction, handleEdit: (prompt: IPrompt) => void): ColumnsType<IPrompt> => [
  {
    title: t('Prompt_Info_Name'),
    dataIndex: 'prompt_name',
    key: 'prompt_name',
  },
  {
    title: t('Prompt_Info_Scene'),
    dataIndex: 'chat_scene',
    key: 'chat_scene',
  },
  {
    title: t('Prompt_Info_Sub_Scene'),
    dataIndex: 'sub_chat_scene',
    key: 'sub_chat_scene',
  },
  {
    title: t('Prompt_Info_Content'),
    dataIndex: 'content',
    key: 'content',
    render: (content) => (
      <Tooltip placement="topLeft" title={content}>
        {content}
      </Tooltip>
    ),
  },
  {
    title: t('Operation'),
    dataIndex: 'operate',
    key: 'operate',
    render: (_, record) => (
      <Button
        onClick={() => {
          handleEdit(record);
        }}
        type="primary"
      >
        {t('Edit')}
      </Button>
    ),
  },
];

type FormType = Ref<FormInstance<any>> | undefined;

const Prompt = () => {
  const { t } = useTranslation();

  const [promptType, setPromptType] = useState<string>('common');
  const [promptList, setPromptList] = useState<Array<IPrompt>>();
  const [loading, setLoading] = useState<boolean>(false);
  const [prompt, setPrompt] = useState<IPrompt>();
  const [showModal, setShowModal] = useState<boolean>(false);
  const [scenes, setScenes] = useState<Array<Record<string, string>>>();
  const formRef = useRef<FormType>();

  const getPrompts = async () => {
    setLoading(true);
    const body = {
      prompt_type: promptType,
      current: 1,
      pageSize: 1000,
      hideOnSinglePage: true,
      showQuickJumper: true,
    };
    const [_, data] = await apiInterceptors(getPromptList(body));
    setPromptList(data!);
    setLoading(false);
  };

  const getScenes = async () => {
    const [, res] = await apiInterceptors(postScenes());
    setScenes(res?.map((scene) => ({ value: scene.chat_scene, label: scene.scene_name })));
  };

  const onFinish = async (newPrompt: IPrompt) => {
    if (prompt) {
      await apiInterceptors(updatePrompt({ ...newPrompt, prompt_type: promptType }));
    } else {
      await apiInterceptors(addPrompt({ ...newPrompt, prompt_type: promptType }));
    }
    getPrompts();
    handleClose();
  };

  const handleEditBtn = (prompt: IPrompt) => {
    setPrompt(prompt);
    setShowModal(true);
  };

  const handleAddBtn = () => {
    setShowModal(true);
    setPrompt(undefined);
  };

  const handleClose = () => {
    setShowModal(false);
  };

  const handleMenuChange: MenuProps['onClick'] = (e) => {
    const type = e.key;
    setPromptType(type);
  };

  useEffect(() => {
    getPrompts();
  }, [promptType]);

  useEffect(() => {
    getScenes();
  }, []);

  return (
    <div>
      <Menu onClick={handleMenuChange} selectedKeys={[promptType]} mode="horizontal" items={getItems(t)} />
      <div className="px-6 py-4">
        <div className="flex flex-row-reverse mb-4">
          <Button className="flex items-center" onClick={handleAddBtn}>
            <PlusOutlined />
            {t('Add')} Prompts
          </Button>
          {promptType === 'common' && (
            <Button className="mr-2 flex items-center" disabled>
              <PlusOutlined />
              {t('Add')} Prompts {t('template')}
            </Button>
          )}
        </div>
        <Table
          columns={getColumns(t, handleEditBtn)}
          dataSource={promptList}
          loading={loading}
          rowKey={(record) => record.prompt_name}
          scroll={{ y: 600 }}
        />
      </div>
      <Modal
        title={`${prompt ? t('Edit') : t('Add')} Prompts`}
        destroyOnClose
        open={showModal}
        onCancel={handleClose}
        cancelText={t('cancel')}
        okText={t('submit')}
        onOk={() => {
          // @ts-ignore
          formRef.current?.submit();
        }}
      >
        <PromptForm scenes={scenes} ref={formRef as FormType} prompt={prompt} onFinish={onFinish} />
      </Modal>
    </div>
  );
};

export default Prompt;
