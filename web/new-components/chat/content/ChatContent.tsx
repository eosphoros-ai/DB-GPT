import markdownComponents from '@/components/chat/chat-content/config';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import { CheckOutlined, ClockCircleOutlined, CloseOutlined, CodeOutlined, LoadingOutlined } from '@ant-design/icons';
import classNames from 'classnames';
import Image from 'next/image';
import { useSearchParams } from 'next/navigation';
import React, { memo, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { GPTVis } from '@antv/gpt-vis';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';

import Feedback from './Feedback';
import RobotIcon from './RobotIcon';

const UserIcon: React.FC = () => {
  const user = JSON.parse(localStorage.getItem(STORAGE_USERINFO_KEY) ?? '');

  if (!user.avatar_url) {
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-tr from-[#31afff] to-[#1677ff] text-xs text-white">
        {user?.nick_name}
      </div>
    );
  }
  return (
    <Image
      className="rounded-full border border-gray-200 object-contain bg-white inline-block"
      width={32}
      height={32}
      src={user?.avatar_url}
      alt={user?.nick_name}
    />
  );
};

type DBGPTView = {
  name: string;
  status: 'todo' | 'runing' | 'failed' | 'completed' | (string & {});
  result?: string;
  err_msg?: string;
};

type MarkdownComponent = Parameters<typeof GPTVis>["0"]["components"];

const pluginViewStatusMapper: Record<DBGPTView['status'], { bgClass: string; icon: React.ReactNode }> = {
  todo: {
    bgClass: 'bg-gray-500',
    icon: <ClockCircleOutlined className="ml-2" />,
  },
  runing: {
    bgClass: 'bg-blue-500',
    icon: <LoadingOutlined className="ml-2" />,
  },
  failed: {
    bgClass: 'bg-red-500',
    icon: <CloseOutlined className="ml-2" />,
  },
  completed: {
    bgClass: 'bg-green-500',
    icon: <CheckOutlined className="ml-2" />,
  },
};

const formatMarkdownVal = (val: string) => {
  return val
    .replaceAll('\\n', '\n')
    .replace(/<table(\w*=[^>]+)>/gi, '<table $1>')
    .replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
};

const formatMarkdownValForAgent = (val: string) => {
  return val?.replace(/<table(\w*=[^>]+)>/gi, '<table $1>').replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
};

const ChatContent: React.FC<{
  content: Omit<IChatDialogueMessageSchema, 'context'> & {
    context:
      | string
      | {
          template_name: string;
          template_introduce: string;
        };
  };
  onLinkClick: () => void;
}> = ({ content, onLinkClick }) => {
  const { t } = useTranslation();

  const searchParams = useSearchParams();
  const scene = searchParams?.get('scene') ?? '';

  const { context, model_name, role, thinking } = content;

  const isRobot = useMemo(() => role === 'view', [role]);

  const { relations, value, cachePluginContext } = useMemo<{ relations: string[]; value: string; cachePluginContext: DBGPTView[] }>(() => {
    if (typeof context !== 'string') {
      return {
        relations: [],
        value: '',
        cachePluginContext: [],
      };
    }
    const [value, relation] = context.split('\trelations:');
    const relations = relation ? relation.split(',') : [];
    const cachePluginContext: DBGPTView[] = [];

    let cacheIndex = 0;
    const result = value.replace(/<dbgpt-view[^>]*>[^<]*<\/dbgpt-view>/gi, (matchVal) => {
      try {
        const pluginVal = matchVal.replaceAll('\n', '\\n').replace(/<[^>]*>|<\/[^>]*>/gm, '');
        const pluginContext = JSON.parse(pluginVal) as DBGPTView;
        const replacement = `<custom-view>${cacheIndex}</custom-view>`;

        cachePluginContext.push({
          ...pluginContext,
          result: formatMarkdownVal(pluginContext.result ?? ''),
        });
        cacheIndex++;

        return replacement;
      } catch (e) {
        console.log((e as any).message, e);
        return matchVal;
      }
    });
    return {
      relations,
      cachePluginContext,
      value: result,
    };
  }, [context]);

  const extraMarkdownComponents = useMemo<MarkdownComponent>(
    () => ({
      'custom-view'({ children }) {
        const index = +children.toString();
        if (!cachePluginContext[index]) {
          return children;
        }
        const { name, status, err_msg, result } = cachePluginContext[index];
        const { bgClass, icon } = pluginViewStatusMapper[status] ?? {};
        return (
          <div className="bg-white dark:bg-[#212121] rounded-lg overflow-hidden my-2 flex flex-col lg:max-w-[80%]">
            <div
              className={classNames(
                "flex px-4 md:px-6 py-2 items-center text-white text-sm",
                bgClass
              )}
            >
              {name}
              {icon}
            </div>
            {result ? (
              <div className="px-4 md:px-6 py-4 text-sm">
                <GPTVis
                  components={markdownComponents}
                  rehypePlugins={[rehypeRaw]}
                  remarkPlugins={[remarkGfm]}
                >
                  {result ?? ""}
                </GPTVis>
              </div>
            ) : (
              <div className="px-4 md:px-6 py-4 text-sm">{err_msg}</div>
            )}
          </div>
        );
      },
    }),
    [cachePluginContext],
  );

  return (
    <div className="flex flex-1 gap-3 mt-6">
      {/* icon */}
      <div className="flex flex-shrink-0 items-start">
        {isRobot ? <RobotIcon model={model_name} /> : <UserIcon />}
      </div>
      <div
        className={`flex ${
          scene === "chat_agent" && !thinking ? "flex-1" : ""
        } overflow-hidden`}
      >
        {/* 用户提问 */}
        {!isRobot && (
          <div className="flex flex-1 items-center text-sm text-[#1c2533] dark:text-white">
            {typeof context === "string" && context}
          </div>
        )}
        {/* ai回答 */}
        {isRobot && (
          <div className="flex flex-1 flex-col w-full">
            <div className="bg-white dark:bg-[rgba(255,255,255,0.16)] p-4 rounded-2xl rounded-tl-none mb-2">
              {typeof context === "object" && (
                <div>
                  {`[${context.template_name}]: `}
                  <span
                    className="text-theme-primary cursor-pointer"
                    onClick={onLinkClick}
                  >
                    <CodeOutlined className="mr-1" />
                    {context.template_introduce || "More Details"}
                  </span>
                </div>
              )}
              {typeof context === "string" && scene === "chat_agent" && (
                <GPTVis
                  components={{ ...markdownComponents }}
                  rehypePlugins={[rehypeRaw]}
                  remarkPlugins={[remarkGfm]}
                >
                  {formatMarkdownValForAgent(value)}
                </GPTVis>
              )}
              {typeof context === "string" && scene !== "chat_agent" && (
                <div>
                  <GPTVis
                    components={{
                      ...markdownComponents,
                      ...extraMarkdownComponents,
                    }}
                    rehypePlugins={[rehypeRaw]}
                    remarkPlugins={[remarkGfm]}
                  >
                    {formatMarkdownVal(value)}
                  </GPTVis>
                </div>
              )}
              {/* 正在思考 */}
              {thinking && !context && (
                <div className="flex items-center gap-2">
                  <span className="flex text-sm text-[#1c2533] dark:text-white">
                    {t("thinking")}
                  </span>
                  <div className="flex">
                    <div className="w-1 h-1 rounded-full mx-1 animate-pulse1"></div>
                    <div className="w-1 h-1 rounded-full mx-1 animate-pulse2"></div>
                    <div className="w-1 h-1 rounded-full mx-1 animate-pulse3"></div>
                  </div>
                </div>
              )}
            </div>
            {/* 用户反馈 */}
            <Feedback content={content} />
          </div>
        )}
      </div>
    </div>
  );
};

export default memo(ChatContent);
