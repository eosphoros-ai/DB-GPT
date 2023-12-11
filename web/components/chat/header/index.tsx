import { useContext } from 'react';
import ChatExcel from './chat-excel';
import { ChatContext } from '@/app/chat-context';
import ModeTab from '@/components/chat/mode-tab';
import ModelSelector from '@/components/chat/header/model-selector';
import DBSelector from './db-selector';
import AgentSelector from './agent-selector';

/**
 * chat header
 */
interface Props {
  refreshHistory?: () => Promise<void>;
  modelChange?: (val: string) => void;
}

function Header({ refreshHistory, modelChange }: Props) {
  const { scene, refreshDialogList } = useContext(ChatContext);

  return (
    <div className="w-full py-2 px-4 md:px-4 flex flex-wrap items-center justify-center border-b border-gray-100 gap-1 md:gap-4">
      {/* Models Selector */}
      <ModelSelector onChange={modelChange} />
      {/* DB Selector */}
      <DBSelector />
      {/* Excel Upload */}
      {scene === 'chat_excel' && (
        <ChatExcel
          onComplete={() => {
            refreshDialogList?.();
            refreshHistory?.();
          }}
        />
      )}
      {/* Agent Selector */}
      {scene === 'chat_agent' && <AgentSelector />}
      <ModeTab />
    </div>
  );
}

export default Header;
