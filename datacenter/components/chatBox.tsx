import { zodResolver } from '@hookform/resolvers/zod';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { Card, CircularProgress, IconButton, Input, Stack, Select, Option, Tooltip } from '@/lib/mui';
import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Message } from '@/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import Markdown from 'markdown-to-jsx';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { okaidia } from 'react-syntax-highlighter/dist/esm/styles/prism';

type Props = {
  messages: Message[];
  onSubmit: (message: string, otherQueryBody?: any) => Promise<any>;
  initialMessage?: string;
  readOnly?: boolean;
  paramsList?: { [key: string]: string };
  clearIntialMessage?: () => void;
}; 

const Schema = z.object({ query: z.string().min(1) });

const ChatBoxComp = ({
  messages,
  onSubmit,
  initialMessage,
  readOnly,
  paramsList,
  clearIntialMessage
}: Props) => {
  const scrollableRef = React.useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [firstMsg, setFirstMsg] = useState<Message>();
  const [currentParam, setCurrentParam] = useState<string | undefined | null>();

  const methods = useForm<z.infer<typeof Schema>>({
    resolver: zodResolver(Schema),
    defaultValues: {},
  });

  const submit = async ({ query }: z.infer<typeof Schema>) => {
    try {
      setIsLoading(true);
      methods.reset();
      await onSubmit(query, {
        select_param: paramsList?.[currentParam]
      });
    } catch (err) {
    } finally {
      setIsLoading(false);
    }
  };

  const handleInitMessage = async () => {
    try {
      const searchParams = new URLSearchParams(window.location.search);
      searchParams.delete('initMessage');
      window.history.replaceState(null, null, `?${searchParams.toString()}`);
      await submit({ query: (initialMessage as string) });
    } catch (err) {
      console.log(err);
    } finally {
      clearIntialMessage?.();
    }
  }

  const options = {
    overrides: {
      code: ({ children }) => (
        <SyntaxHighlighter language="javascript" style={okaidia}>
          {children}
        </SyntaxHighlighter>
      ),
    },
  };

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

  React.useEffect(() => {
    if (paramsList && Object.keys(paramsList || {})?.length > 0) {
      setCurrentParam(Object.keys(paramsList || {})?.[0]);
    }
  }, [paramsList]);

  return (
    <div className='mx-auto flex h-full max-w-3xl flex-col gap-6 px-5 py-6 sm:gap-8 xl:max-w-5xl'>
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

          {messages.filter(item => ['view', 'human'].includes(item.role)).map((each, index) => (
            <Stack
              key={index}
              sx={{
                mr: each.role === 'view' ? 'auto' : 'none',
                ml: each.role === 'human' ? 'auto' : 'none',
              }}
            >
              <Card
                size="sm"
                variant={'outlined'}
                className={
                  each.role === 'view' ? 'message-agent' : 'message-human'
                }
                color={each.role === 'view' ? 'primary' : 'neutral'}
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
                <Markdown options={options}>
                  {each.context?.replaceAll('\\n', '\n')}
                </Markdown>
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
              flexDirection: 'column',
              gap: '12px'
            }}
            onSubmit={(e) => {
              e.stopPropagation();
              methods.handleSubmit(submit)(e);
            }}
          >
            {(Object.keys(paramsList || {}).length > 0) && (
              <div className='flex items-center gap-3'>
                <Select
                  value={currentParam}
                  onChange={(e, newValue) => {
                    setCurrentParam(newValue);
                  }}
                  className='max-w-xs'
                >
                  {Object.keys(paramsList || {}).map(paramItem => (
                    <Option
                      key={paramItem}
                      value={paramItem}
                    >
                      {paramsList?.[paramItem]}
                    </Option>
                  ))}
                </Select>
                <Tooltip
                  className="cursor-pointer"
                  title={currentParam}
                  placement="top"
                  variant="outlined"
                >
                  <InfoOutlinedIcon />
                </Tooltip>
              </div>
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
    </div>
    
  );
}

export default ChatBoxComp;
