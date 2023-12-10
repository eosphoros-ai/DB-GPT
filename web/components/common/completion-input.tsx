import { SendOutlined } from '@ant-design/icons';
import { Button, Input } from 'antd';
import { PropsWithChildren, useContext, useEffect, useMemo, useRef, useState } from 'react';
import PromptBot from './prompt-bot';
import DocUpload from '../chat/doc-upload';
import DocList from '../chat/doc-list';
import { IDocument } from '@/types/knowledge';
import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getDocumentList } from '@/client/api';

type TextAreaProps = Omit<Parameters<typeof Input.TextArea>[0], 'value' | 'onPressEnter' | 'onChange' | 'onSubmit'>;

interface Props {
  loading?: boolean;
  onSubmit: (val: string) => void;
  handleFinish?: (val: boolean) => void;
}

function CompletionInput({ children, loading, onSubmit, handleFinish, ...props }: PropsWithChildren<Props & TextAreaProps>) {
  const { dbParam, scene } = useContext(ChatContext);

  const [userInput, setUserInput] = useState('');
  const showUpload = useMemo(() => scene === 'chat_knowledge', [scene]);
  const [documents, setDocuments] = useState<IDocument[]>([]);
  const uploadCountRef = useRef(0);

  useEffect(() => {
    showUpload && fetchDocuments();
  }, [dbParam]);

  async function fetchDocuments() {
    if (!dbParam) {
      return null;
    }
    const [_, data] = await apiInterceptors(
      getDocumentList(dbParam, {
        page: 1,
        page_size: uploadCountRef.current,
      }),
    );
    setDocuments(data?.data!);
  }

  const onUploadFinish = () => {
    uploadCountRef.current += 1;
    fetchDocuments();
  };

  return (
    <div className="flex-1 relative">
      <DocList documents={documents} dbParam={dbParam} />
      {showUpload && <DocUpload handleFinish={handleFinish} onUploadFinish={onUploadFinish} className="absolute z-10 top-2 left-2" />}
      <Input.TextArea
        className={`flex-1 ${showUpload ? 'pl-10' : ''} pr-10`}
        size="large"
        value={userInput}
        autoSize={{ minRows: 1, maxRows: 4 }}
        {...props}
        onPressEnter={(e) => {
          if (!userInput.trim()) return;
          if (e.keyCode === 13) {
            if (e.shiftKey) {
              setUserInput((state) => state + '\n');
              return;
            }
            onSubmit(userInput);
            setTimeout(() => {
              setUserInput('');
            }, 0);
          }
        }}
        onChange={(e) => {
          if (typeof props.maxLength === 'number') {
            setUserInput(e.target.value.substring(0, props.maxLength));
            return;
          }
          setUserInput(e.target.value);
        }}
      />
      <Button
        className="ml-2 flex items-center justify-center absolute right-2 bottom-0"
        size="large"
        type="text"
        loading={loading}
        icon={<SendOutlined />}
        onClick={() => {
          onSubmit(userInput);
        }}
      />
      <PromptBot
        submit={(prompt) => {
          setUserInput(userInput + prompt);
        }}
      />
      {children}
    </div>
  );
}

export default CompletionInput;
