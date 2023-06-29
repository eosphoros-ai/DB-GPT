import { zodResolver } from '@hookform/resolvers/zod';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import Button from '@mui/joy/Button';
import Card from '@mui/joy/Card';
import CircularProgress from '@mui/joy/CircularProgress';
import IconButton from '@mui/joy/IconButton';
import Input from '@mui/joy/Input';
import Stack from '@mui/joy/Stack';
import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { z } from 'zod';
import { Message } from '@/types';

type Props = {
  messages: Message[];
  onSubmit: (message: string) => Promise<any>;
  messageTemplates?: string[];
  initialMessage?: string;
  readOnly?: boolean;
  clearIntialMessage?: () => void;
}; 

const Schema = z.object({ query: z.string().min(1) });

const ChatBoxComp = ({
  messages,
  onSubmit,
  messageTemplates,
  initialMessage,
  readOnly,
  clearIntialMessage
}: Props) => {
  const scrollableRef = React.useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [firstMsg, setFirstMsg] = useState<Message>();
  const [hideTemplateMessages, setHideTemplateMessages] = useState(false);

  const methods = useForm<z.infer<typeof Schema>>({
    resolver: zodResolver(Schema),
    defaultValues: {},
  });

  const submit = async ({ query }: z.infer<typeof Schema>) => {
    try {
      setIsLoading(true);
      setHideTemplateMessages(true);
      methods.reset();
      await onSubmit(query);
    } catch (err) {
    } finally {
      setIsLoading(false);
    }
  };

  const handleInitMessage = async () => {
    await submit({ query: (initialMessage as string) });
    clearIntialMessage?.();
  }

  React.useEffect(() => {
    if (!scrollableRef.current) {
      return;
    }

    scrollableRef.current.scrollTo(0, scrollableRef.current.scrollHeight);
  }, [messages?.length]);

  React.useEffect(() => {
    if (initialMessage && messages.length <= 0) {
      handleInitMessage();
    }
  }, [initialMessage]);

  return (
    <Stack
      direction={'column'}
      gap={2}
      sx={{
        display: 'flex',
        flex: 1,
        flexBasis: '100%',
        width: '100%',
        height: '100%',
        maxHeight: '100%',
        minHeight: '100%',
        mx: 'auto',
      }}
    >
      <Stack
        ref={scrollableRef}
        direction={'column'}
        gap={2}
        sx={{
          boxSizing: 'border-box',
          maxWidth: '100%',
          width: '100%',
          mx: 'auto',
          flex: 1,
          maxHeight: '100%',
          overflowY: 'auto',
          p: 2,
					border: '1px solid',
					borderColor: 'var(--joy-palette-divider)'
        }}
      >
        {firstMsg && (
          <Card
            size="sm"
            variant={'outlined'}
            color={'primary'}
            className="message-agent"
            sx={{
              mr: 'auto',
              ml: 'none',
              whiteSpace: 'pre-wrap',
            }}
          >
            {firstMsg?.context}
          </Card>
        )}

        {messages.filter(item => ['ai', 'human'].includes(item.role)).map((each, index) => (
          <Stack
            key={index}
            sx={{
              mr: each.role === 'ai' ? 'auto' : 'none',
              ml: each.role === 'human' ? 'auto' : 'none',
            }}
          >
            <Card
              size="sm"
              variant={'outlined'}
              className={
                each.role === 'ai' ? 'message-agent' : 'message-human'
              }
              color={each.role === 'ai' ? 'primary' : 'neutral'}
              sx={(theme) => ({
                px: 2,
                'ol, ul': {
                  my: 0,
                  pl: 2,
                },
                ol: {
                  listStyle: 'numeric',
                },
                ul: {
                  listStyle: 'disc',
                  mb: 2,
                },
                li: {
                  my: 1,
                },
                a: {
                  textDecoration: 'underline',
                },
              })}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} linkTarget={'_blank'}>
                {each.context}
              </ReactMarkdown>
            </Card>
          </Stack>
        ))}

        {isLoading && (
          <CircularProgress
            variant="soft"
            color="neutral"
            size="sm"
            sx={{ mx: 'auto', my: 2 }}
          />
        )}
      </Stack>
      {!readOnly && (
        <form
          style={{
            maxWidth: '100%',
            width: '100%',
            position: 'relative',
            display: 'flex',
            marginTop: 'auto',
            overflow: 'visible',
            background: 'none',
            justifyContent: 'center',
            marginLeft: 'auto',
            marginRight: 'auto',
          }}
          onSubmit={(e) => {
            e.stopPropagation();

            methods.handleSubmit(submit)(e);
          }}
        >
          {!hideTemplateMessages && (messageTemplates?.length || 0) > 0 && (
            <Stack
              direction="row"
              gap={1}
              sx={{
                position: 'absolute',
                zIndex: 1,
                transform: 'translateY(-100%)',
                flexWrap: 'wrap',
                mt: -1,
                left: '0',
              }}
            >
              {messageTemplates?.map((each, idx) => (
                <Button
                  key={idx}
                  size="sm"
                  variant="soft"
                  onClick={() => submit({ query: each })}
                >
                  {each}
                </Button>
              ))}
            </Stack>
          )}

          <Input
            sx={{ width: '100%' }}
            variant="outlined"
            endDecorator={
              <IconButton type="submit" disabled={isLoading}>
                <SendRoundedIcon />
              </IconButton>
            }
            {...methods.register('query')}
          />
        </form>
      )}
    </Stack>
  );
}

export default ChatBoxComp;
