import { useRequest } from 'ahooks';
import { useContext, useState } from 'react';
import { Divider, Spin, Tag } from 'antd';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { NextPage } from 'next';
import { apiInterceptors, newDialogue, postScenes } from '@/client/api';
import ModelSelector from '@/components/chat/header/model-selector';
import { ChatContext } from '@/app/chat-context';
import { SceneResponse } from '@/types/chat';
import CompletionInput from '@/components/common/completion-input';
import { useTranslation } from 'react-i18next';
import { STORAGE_INIT_MESSAGE_KET } from '@/utils';
import Icon from '@ant-design/icons/lib/components/Icon';
import { ColorfulDB, ColorfulPlugin, ColorfulDashboard, ColorfulData, ColorfulExcel, ColorfulDoc } from '@/components/icons';
import classNames from 'classnames';

const Home: NextPage = () => {
  const router = useRouter();
  const { model, setModel } = useContext(ChatContext);
  const { t } = useTranslation();

  const [loading, setLoading] = useState(false);
  const [chatSceneLoading, setChatSceneLoading] = useState<boolean>(false);

  const { data: scenesList = [] } = useRequest(async () => {
    setChatSceneLoading(true);
    const [, res] = await apiInterceptors(postScenes());
    setChatSceneLoading(false);
    return res ?? [];
  });

  const submit = async (message: string) => {
    setLoading(true);
    const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_normal' }));
    if (res) {
      localStorage.setItem(STORAGE_INIT_MESSAGE_KET, JSON.stringify({ id: res.conv_uid, message }));
      router.push(`/chat/?scene=chat_normal&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
    }
    setLoading(false);
  };

  const handleNewChat = async (scene: SceneResponse) => {
    if (scene.show_disable) return;
    const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_normal' }));
    if (res) {
      router.push(`/chat?scene=${scene.chat_scene}&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
    }
  };

  function renderSceneIcon(scene: string) {
    switch (scene) {
      case 'chat_knowledge':
        return <Icon className="w-10 h-10 mr-4 p-1 bg-white rounded" component={ColorfulDoc} />;
      case 'chat_with_db_execute':
        return <Icon className="w-10 h-10 mr-4 p-1 bg-white rounded" component={ColorfulData} />;
      case 'chat_excel':
        return <Icon className="w-10 h-10 mr-4 p-1 bg-white rounded" component={ColorfulExcel} />;
      case 'chat_with_db_qa':
        return <Icon className="w-10 h-10 mr-4 p-1 bg-white rounded" component={ColorfulDB} />;
      case 'chat_dashboard':
        return <Icon className="w-10 h-10 mr-4 p-1 bg-white rounded" component={ColorfulDashboard} />;
      case 'chat_agent':
        return <Icon className="w-10 h-10 mr-4 p-1 bg-white rounded" component={ColorfulPlugin} />;
      default:
        return null;
    }
  }

  return (
    <div className="px-4 h-screen flex flex-col justify-center items-center overflow-hidden">
      <div className="max-w-3xl max-h-screen overflow-y-auto">
        <Image
          src="/LOGO.png"
          alt="Revolutionizing Database Interactions with Private LLM Technology"
          width={856}
          height={160}
          className="w-full mt-4"
          unoptimized
        />
        <Divider className="!text-[#878c93] !my-6" plain>
          {t('Quick_Start')}
        </Divider>
        <Spin spinning={chatSceneLoading}>
          <div className="flex flex-wrap -m-1 md:-m-2">
            {scenesList.map((scene) => (
              <div
                key={scene.chat_scene}
                className="w-full sm:w-1/2 p-1 md:p-2"
                onClick={() => {
                  handleNewChat(scene);
                }}
              >
                <div
                  className={classNames(
                    'flex flex-row justify-center min-h-min border bg-slate-50 border-gray-300 dark:bg-black bg-opacity-50 border-opacity-50 text-gray-950 dark:text-white rounded p-4 cursor-pointer',
                    { 'grayscale !cursor-no-drop': scene.show_disable },
                  )}
                >
                  {renderSceneIcon(scene.chat_scene)}
                  <div className="flex flex-col flex-1">
                    <h2 className="flex items-center text-lg font-sans font-semibold">
                      {scene.scene_name}
                      {scene.show_disable && <Tag className="ml-2">Comming soon</Tag>}
                    </h2>
                    <p className="opacity-80 line-clamp-2">{scene.scene_describe}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Spin>
        <div className="mt-8 mb-2">
          <ModelSelector
            onChange={(newModel: string) => {
              setModel(newModel);
            }}
          />
        </div>
        <div className="flex flex-1 w-full mb-4">
          <CompletionInput loading={loading} onSubmit={submit} />
        </div>
      </div>
    </div>
  );
};

export default Home;
