"use client";

import ReactMarkdown from 'react-markdown';
import { Collapse } from 'antd';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { Box, Slider, Input, Tabs, TabList, Typography, TabPanel, Tab, RadioGroup, Radio, tabClasses, useColorScheme, radioClasses } from '@/lib/mui';
import { sendGetRequest } from '@/utils/request';
import { useEffect, useState } from 'react';
import ChatBoxComp from '@/components/chatBox';
import useAgentChat from '@/hooks/useAgentChat';

export default function Home() {
  const [temperatureNum, setTemperatureNum] = useState(3);
  const [tokenSize, setTokenSize] = useState(0);
  const { mode, setMode } = useColorScheme();

  const { handleChatSubmit, history } = useAgentChat({
    queryAgentURL: `/api/agents/query`,
  });

  const handleGetD = () => {
    sendGetRequest('/v1/chat/dialogue/list', {
    })
  }
  console.log(mode, 'mode', radioClasses, 'radioClasses')
  useEffect(() => {
    handleGetD();
  }, []);
  return (
    <div className='p-6 w-full h-full text-sm flex flex-col gap-4'>
      <ReactMarkdown linkTarget={'_blank'}>
        [DB-GPT](https://github.com/csunny/DB-GPT) 是一个开源的以数据库为基础的GPT实验项目，使用本地化的GPT大模型与您的数据和环境进行交互，无数据泄露风险，100% 私密，100% 安全。
      </ReactMarkdown>
      <Box
        sx={{
          '& .ant-collapse': {
            backgroundColor: 'var(--joy-palette-background-level1)',
            color: 'var(--joy-palette-neutral-plainColor)'
          },
          '& .ant-collapse>.ant-collapse-item >.ant-collapse-header, & .ant-collapse .ant-collapse-content': {
            color: 'var(--joy-palette-neutral-plainColor)'
          },
          '& .ant-collapse .ant-collapse-content>.ant-collapse-content-box': {
            paddingTop: 0
          }
        }}
      >
        <Collapse
          collapsible="header"
          defaultActiveKey={['1']}
          ghost
          bordered
          expandIcon={({ isActive }) => (
            <div className={`text-2xl cursor-pointer ${isActive ? 'rotate-0' : 'rotate-90'}`}>
              <ArrowDropDownIcon />
            </div>
          )}
          expandIconPosition="end"
          items={[
            {
              key: '1',
              label: 'This panel can only be collapsed by clicking text',
              children: (
                <>
                  <Box
                    className="p-4 border"
                    sx={{
                      borderColor: 'var(--joy-palette-background-level2)',
                    }}
                  >
                    <div className='flex flex-row justify-between items-center'>
                      <span>Temperature</span>
                      <Input
                        size='sm'
                        type="number"
                        value={temperatureNum / 10}
                        onChange={(e) => {
                          console.log(Number(e.target.value) * 10, '===')
                          setTemperatureNum(Number(e.target.value) * 10);
                        }}
                        slotProps={{
                          input: {
                            min: 0,
                            max: 1,
                            step: 0.1,
                          },
                        }}
                      />
                    </div>
                    <Slider
                      color="info"
                      value={temperatureNum}
                      max={10}
                      onChange={(e, value) => {
                        console.log(e, 'e', value, 'v')
                        setTemperatureNum(value);
                      }}
                    />
                  </Box>
                  <Box
                    className="p-4 border border-t-0"
                    sx={{
                      borderColor: 'var(--joy-palette-background-level2)',
                    }}
                  >
                    <div className='flex flex-row justify-between items-center'>
                      <span>Maximum output token size</span>
                      <Input
                        size="sm"
                        type="number"
                        value={tokenSize}
                        onChange={(e) => {
                          setTokenSize(Number(e.target.value));
                        }}
                        slotProps={{
                          input: {
                            min: 0,
                            max: 1024,
                            step: 64,
                          },
                        }}
                      />
                    </div>
                    <Slider
                      color="info"
                      value={tokenSize}
                      max={1024}
                      step={64}
                      onChange={(e, value) => {
                        console.log(e, 'e', value, 'v')
                        setTokenSize(value);
                      }}
                    />
                  </Box>
                </>
              ),
            },
          ]}
        />
      </Box>
      <Box>
        <Tabs
          className='w-full'
          aria-label="Pricing plan"
          defaultValue={0}
          sx={(theme) => ({
            '--Tabs-gap': '0px',
            borderRadius: 'unset',
            boxShadow: 'sm',
            overflow: 'auto',
            WebkitBoxShadow: 'none'
          })}
        >
          <TabList
            sx={{
              '--ListItem-radius': '0px',
              borderRadius: 0,
              bgcolor: 'background.body',
              [`& .${tabClasses.root}`]: {
                fontWeight: 'lg',
                flex: 'unset',
                position: 'relative',
                [`&.${tabClasses.selected}`]: {
                  border: '1px solid var(--joy-palette-background-level2)',
                  borderTopLeftRadius: '8px',
                  borderTopRightRadius: '8px',
                },
                [`&.${tabClasses.selected}:before`]: {
                  content: '""',
                  display: 'block',
                  position: 'absolute',
                  bottom: -4,
                  width: '100%',
                  height: 6,
                  bgcolor: mode == 'dark' ? '#000' : 'var(--joy-palette-background-surface)',
                },
                [`&.${tabClasses.focusVisible}`]: {
                  outlineOffset: '-3px',
                },
              },
            }}
          >
            <Tab sx={{ py: 1.5 }}>Documents Chat</Tab>
            <Tab>SQL Generation & Diagnostics</Tab>
            <Tab>Plugin Mode</Tab>
          </TabList>
          <TabPanel 
            value={0} 
            sx={{ 
              p: 3,
              border: '1px solid var(--joy-palette-background-level2)',
              borderBottomLeftRadius: '8px',
              borderBottomRightRadius: '8px',
            }}
          >
            <RadioGroup
              orientation="horizontal"
              defaultValue="LLM native dialogue"
              name="radio-buttons-group"
              className='gap-3 p-3'
              sx={{
                backgroundColor: 'var(--joy-palette-background-level1)',
                '& .MuiRadio-radio': {
                  borderColor: '#707070'
                },
              }}
            >
              <Box className="px-2 py-1 border rounded" sx={{ borderColor: 'var(--joy-palette-background-level2)' }}>
                <Radio value="LLM native dialogue" label="LLM native dialogue" variant="outlined"
                  sx={{ 
                    borderColor: 'var(--joy-palette-neutral-outlinedHoverColor)',
                  }} 
                />
              </Box>
              <Box className="px-2 py-1 border rounded" sx={{ borderColor: 'var(--joy-palette-background-level2)' }}>
                <Radio value="Default documents" label="Default documents" variant="outlined" />
              </Box>
              <Box className="px-2 py-1 border rounded" sx={{ borderColor: 'var(--joy-palette-background-level2)' }}>
                <Radio value="New documents" label="New documents" variant="outlined" />
              </Box>
              <Box className="px-2 py-1 border rounded" sx={{ borderColor: 'var(--joy-palette-background-level2)' }}>
                <Radio value="Chat with url" label="Chat with url" variant="outlined" />
              </Box>
            </RadioGroup>
          </TabPanel>
          <TabPanel value={1} sx={{ p: 3 }}>
            <Typography level="inherit">
              Best for professional developers building enterprise or data-rich
              applications.
            </Typography>
            <Typography textColor="primary.400" fontSize="xl3" fontWeight="xl" my={1}>
              $15{' '}
              <Typography fontSize="sm" textColor="text.secondary" fontWeight="md">
                / dev / month
              </Typography>
            </Typography>
          </TabPanel>
          <TabPanel value={2} sx={{ p: 3 }}>
            <Typography level="inherit">
              The most advanced features for data-rich applications, as well as the
              highest priority for support.
            </Typography>
            <Typography textColor="primary.400" fontSize="xl3" fontWeight="xl" my={1}>
              <Typography
                fontSize="xl"
                borderRadius="sm"
                px={0.5}
                mr={0.5}
                sx={(theme) => ({
                  ...theme.variants.soft.danger,
                  color: 'danger.400',
                  verticalAlign: 'text-top',
                  textDecoration: 'line-through',
                })}
              >
                $49
              </Typography>
              $37*{' '}
              <Typography fontSize="sm" textColor="text.secondary" fontWeight="md">
                / dev / month
              </Typography>
            </Typography>
          </TabPanel> 
        </Tabs>
      </Box>
      <ChatBoxComp messages={history} onSubmit={handleChatSubmit}/>
    </div>
    
  )
}
