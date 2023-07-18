import { zodResolver } from '@hookform/resolvers/zod';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { Card, CircularProgress, IconButton, Input, Stack, Select, Option, Tooltip, Box, useColorScheme } from '@/lib/mui';
import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Message } from '@/types';
import FaceRetouchingNaturalOutlinedIcon from '@mui/icons-material/FaceRetouchingNaturalOutlined';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import Markdown from 'markdown-to-jsx';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { okaidia } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useSearchParams } from 'next/navigation';

type Props = {
  messages: Message[];
  onSubmit: (message: string, otherQueryBody?: any) => Promise<any>;
  readOnly?: boolean;
  paramsList?: { [key: string]: string };
  clearIntialMessage?: () => void;
}; 

const Schema = z.object({ query: z.string().min(1) });

const ChatBoxComp = ({
  messages,
  onSubmit,
  readOnly,
  paramsList,
  clearIntialMessage
}: Props) => {
  const searchParams = useSearchParams();
  const initMessage = searchParams.get('initMessage');
  const scrollableRef = React.useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentParam, setCurrentParam] = useState<string | undefined | null>();

  const methods = useForm<z.infer<typeof Schema>>({
    resolver: zodResolver(Schema),
    defaultValues: {},
  });

  const submit = async ({ query }: z.infer<typeof Schema>) => {
    try {
      console.log('submit');
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
      const searchParamsTemp = new URLSearchParams(window.location.search);
      const initMessage = searchParamsTemp.get('initMessage');
      searchParamsTemp.delete('initMessage');
      window.history.replaceState(null, null, `?${searchParamsTemp.toString()}`);
      await submit({ query: (initMessage as string) });
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
    wrapper: React.Fragment,
  };

  React.useEffect(() => {
    if (!scrollableRef.current) {
      return;
    }

    scrollableRef.current.scrollTo(0, scrollableRef.current.scrollHeight);
  }, [messages?.length]);
  
  React.useEffect(() => {
    if (initMessage && messages.length <= 0) {
      handleInitMessage();
    }
  }, [initMessage, messages.length]);

  React.useEffect(() => {
    if (paramsList && Object.keys(paramsList || {})?.length > 0) {
      setCurrentParam(Object.keys(paramsList || {})?.[0]);
    }
  }, [paramsList]);

  return (
    <div className='w-full h-full'>
      <Stack
        className="w-full h-full bg-[#fefefe] dark:bg-[#212121]"
        sx={{
          'table': {
            borderCollapse: 'collapse',
            border: '1px solid #ccc',
            width: '100%',
          },
          'th, td': {
            border: '1px solid #ccc',
            padding: '10px',
            textAlign: 'center'
          },
        }}
      >
        <Stack
          ref={scrollableRef}
          direction={'column'}
          sx={{
            overflowY: 'auto',
            maxHeight: '100%',
            flex: 1
          }}
        >
          {messages.filter(item => ['view', 'human'].includes(item.role))?.map((each, index) => {
            return (
              <Stack
                key={index}
              >
                <Card
                  size="sm"
                  variant={'outlined'}
                  color={each.role === 'view' ? 'primary' : 'neutral'}
                  sx={(theme) => ({
                    background: each.role === 'view' ? 'var(--joy-palette-primary-softBg, var(--joy-palette-primary-100, #DDF1FF))': 'unset',
                    border: 'unset',
                    borderRadius: 'unset',
                    padding: '24px 0 26px 0',
                    lineHeight: '24px',
                  })}
                >
                  <Box sx={{ width: '76%', margin: '0 auto' }} className="flex flex-row">
                    <div className='mr-3 inline'>
                      {each.role === 'view' ? (
                        <SmartToyOutlinedIcon />
                      ) : (
                        <FaceRetouchingNaturalOutlinedIcon />
                      )}
                    </div>
                    <div className='inline align-middle mt-0.5 max-w-full flex-1 overflow-auto'>
                      <Markdown options={options}>
                        {each.context?.replaceAll('\\n', '\n')}
                      </Markdown>
                    </div>
                  </Box>
                </Card>
              </Stack>
            )
          })}
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
          <Box
            className="bg-[#fefefe] dark:bg-[#212121] before:bg-[#fefefe] before:dark:bg-[#212121]"
            sx={{
              position: 'relative',
              '&::before': {
                content: '" "',
                position: 'absolute',
                top: '-18px',
                left: '0',
                right: '0',
                width: '100%',
                margin: '0 auto',
                height: '20px',
                filter: 'blur(10px)',
                zIndex: 2,
              }
            }}
          >
            <form
              style={{
                maxWidth: '100%',
                width: '76%',
                position: 'relative',
                display: 'flex',
                marginTop: 'auto', 
                overflow: 'visible',
                background: 'none',
                justifyContent: 'center',
                marginLeft: 'auto',
                marginRight: 'auto',
                flexDirection: 'column',
                gap: '12px',
                paddingBottom: '58px',
                paddingTop: '20px'
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
                    sx={{ maxWidth: '100%' }}
                  >
                    {Object.keys(paramsList || {}).map(paramItem => (
                      <Option
                        key={paramItem}
                        value={paramItem}
                      >
                        {paramItem}
                      </Option>
                    ))}
                  </Select>

                </div>
              )}

              <Input
                className='w-full h-12'
                variant="outlined"
                endDecorator={
                  <IconButton type="submit" disabled={isLoading}>
                    <SendRoundedIcon />
                  </IconButton>
                }
                {...methods.register('query')}
              />
            </form>
          </Box>
        )}
      </Stack>
    </div>
  );
}

export default ChatBoxComp;
