'use client'

import { useRouter } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import CheckCircleOutlinedIcon from '@mui/icons-material/CheckCircleOutlined'
import ContentPasteSearchOutlinedIcon from '@mui/icons-material/ContentPasteSearchOutlined'
import type { UploadProps } from 'antd'
import { message, Upload } from 'antd'
import {
  useColorScheme,
  Modal,
  Button,
  Sheet,
  Stack,
  Box,
  Input,
  Textarea,
  Switch,
  Typography,
  styled
} from '@/lib/mui'
import {
  sendSpacePostRequest,
  sendSpaceUploadPostRequest
} from '@/utils/request'

const { Dragger } = Upload

const Item = styled(Sheet)(({ theme }) => ({
  width: '33%',
  backgroundColor:
    theme.palette.mode === 'dark' ? theme.palette.background.level1 : '#fff',
  ...theme.typography.body2,
  padding: theme.spacing(1),
  textAlign: 'center',
  borderRadius: 4,
  color: theme.vars.palette.text.secondary
}))

const stepsOfAddingSpace = [
  'Knowledge Space Config',
  'Choose a Datasource type',
  'Setup the Datasource'
]
const documentTypeList = [
  {
    type: 'text',
    title: 'Text',
    subTitle: 'Fill your raw text'
  },
  {
    type: 'webPage',
    title: 'URL',
    subTitle: 'Fetch the content of a URL'
  },
  {
    type: 'file',
    title: 'Document',
    subTitle:
      'Upload a document, document type can be PDF, CSV, Text, PowerPoint, Word, Markdown'
  }
]

const Index = () => {
  const router = useRouter()
  const { mode } = useColorScheme()
  const [activeStep, setActiveStep] = useState<number>(0)
  const [documentType, setDocumentType] = useState<string>('')
  const [knowledgeSpaceList, setKnowledgeSpaceList] = useState<any>([])
  const [isAddKnowledgeSpaceModalShow, setIsAddKnowledgeSpaceModalShow] =
    useState<boolean>(false)
  const [knowledgeSpaceName, setKnowledgeSpaceName] = useState<string>('')
  const [owner, setOwner] = useState<string>('')
  const [description, setDescription] = useState<string>('')
  const [webPageUrl, setWebPageUrl] = useState<string>('')
  const [documentName, setDocumentName] = useState<any>('')
  const [textSource, setTextSource] = useState<string>('')
  const [text, setText] = useState<string>('')
  const [originFileObj, setOriginFileObj] = useState<any>(null)
  const [synchChecked, setSynchChecked] = useState<boolean>(true)
  const props: UploadProps = {
    name: 'file',
    multiple: false,
    onChange(info) {
      console.log(info)
      if (info.fileList.length === 0) {
        setOriginFileObj(null)
        setDocumentName('')
        return
      }
      setOriginFileObj(info.file.originFileObj)
      setDocumentName(info.file.originFileObj?.name)
    }
  }
  useEffect(() => {
    async function fetchData() {
      const data = await sendSpacePostRequest('/knowledge/space/list', {})
      if (data.success) {
        setKnowledgeSpaceList(data.data)
      }
    }
    fetchData()
  }, [])
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%'
      }}
      className="bg-[#F1F2F5] dark:bg-[#212121]"
    >
      <Box
        className="page-body p-4"
        sx={{
          '&': {
            height: '90%',
            overflow: 'auto'
          },
          '&::-webkit-scrollbar': {
            display: 'none'
          }
        }}
      >
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          sx={{
            '& i': {
              width: '430px',
              marginRight: '30px'
            }
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignContent: 'start',
              boxSizing: 'content-box',
              width: '390px',
              height: '79px',
              padding: '33px 20px 40px',
              marginRight: '30px',
              marginBottom: '30px',
              fontSize: '18px',
              fontWeight: 'bold',
              color: 'black',
              flexShrink: 0,
              flexGrow: 0,
              cursor: 'pointer',
              borderRadius: '16px',
              '&: hover': {
                boxShadow:
                  '0 10px 15px -3px rgba(0,0,0,.1),0 4px 6px -4px rgba(0,0,0,.1);'
              }
            }}
            onClick={() => setIsAddKnowledgeSpaceModalShow(true)}
            className="bg-[#E9EBEE] dark:bg-[#484848]"
          >
            <Box
              sx={{
                width: '32px',
                height: '32px',
                lineHeight: '28px',
                border: '1px solid #2AA3FF',
                textAlign: 'center',
                borderRadius: '5px',
                marginRight: '5px',
                fontWeight: '300',
                color: '#2AA3FF'
              }}
            >
              +
            </Box>
            <Box
              sx={{
                fontSize: '16px'
              }}
            >
              space
            </Box>
          </Box>
          {knowledgeSpaceList.map((item: any, index: number) => (
            <Box
              key={index}
              sx={{
                padding: '30px 20px 40px',
                marginRight: '30px',
                marginBottom: '30px',
                borderTop: '4px solid rgb(84, 164, 248)',
                flexShrink: 0,
                flexGrow: 0,
                cursor: 'pointer',
                borderRadius: '10px',
                '&: hover': {
                  boxShadow:
                    '0 10px 15px -3px rgba(0,0,0,.1),0 4px 6px -4px rgba(0,0,0,.1);'
                }
              }}
              onClick={() => {
                router.push(`/datastores/documents?name=${item.name}`)
              }}
              className="bg-[#FFFFFF] dark:bg-[#484848]"
            >
              <Box
                sx={{
                  fontSize: '18px',
                  marginBottom: '10px',
                  fontWeight: 'bold',
                  color: 'black'
                }}
              >
                <ContentPasteSearchOutlinedIcon
                  sx={{ marginRight: '5px', color: '#2AA3FF' }}
                />
                {item.name}
              </Box>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'flex-start'
                }}
              >
                <Box
                  sx={{
                    width: '130px',
                    flexGrow: 0,
                    flexShrink: 0
                  }}
                >
                  <Box
                    sx={{
                      color: '#2AA3FF'
                    }}
                  >
                    {item.vector_type}
                  </Box>
                  <Box sx={{ fontSize: '12px', color: 'black' }}>Vector</Box>
                </Box>
                <Box
                  sx={{
                    width: '130px',
                    flexGrow: 0,
                    flexShrink: 0
                  }}
                >
                  <Box
                    sx={{
                      color: '#2AA3FF'
                    }}
                  >
                    {item.owner}
                  </Box>
                  <Box sx={{ fontSize: '12px', color: 'black' }}>Owner</Box>
                </Box>
                <Box
                  sx={{
                    width: '130px',
                    flexGrow: 0,
                    flexShrink: 0
                  }}
                >
                  <Box
                    sx={{
                      color: '#2AA3FF'
                    }}
                  >
                    {item.docs || 0}
                  </Box>
                  <Box sx={{ fontSize: '12px', color: 'black' }}>Docs</Box>
                </Box>
              </Box>
            </Box>
          ))}
          <i></i>
          <i></i>
          <i></i>
          <i></i>
          <i></i>
        </Stack>
      </Box>
      <Modal
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          'z-index': 1000
        }}
        open={isAddKnowledgeSpaceModalShow}
        onClose={() => setIsAddKnowledgeSpaceModalShow(false)}
      >
        <Sheet
          variant="outlined"
          sx={{
            width: 800,
            borderRadius: 'md',
            p: 3,
            boxShadow: 'lg'
          }}
        >
          <Box sx={{ width: '100%' }}>
            <Stack spacing={2} direction="row">
              {stepsOfAddingSpace.map((item: any, index: number) => (
                <Item
                  key={item}
                  sx={{
                    fontWeight: activeStep === index ? 'bold' : '',
                    color: activeStep === index ? '#2AA3FF' : ''
                  }}
                >
                  {index < activeStep ? (
                    <CheckCircleOutlinedIcon />
                  ) : (
                    `${index + 1}.`
                  )}
                  {`${item}`}
                </Item>
              ))}
            </Stack>
          </Box>
          {activeStep === 0 ? (
            <>
              <Box sx={{ margin: '30px auto' }}>
                Knowledge Space Name:
                <Input
                  placeholder="Please input the name"
                  onChange={(e: any) => setKnowledgeSpaceName(e.target.value)}
                  sx={{ marginBottom: '20px' }}
                />
                Owner:
                <Input
                  placeholder="Please input the owner"
                  onChange={(e: any) => setOwner(e.target.value)}
                  sx={{ marginBottom: '20px' }}
                />
                Description:
                <Input
                  placeholder="Please input the description"
                  onChange={(e: any) => setDescription(e.target.value)}
                  sx={{ marginBottom: '20px' }}
                />
              </Box>
              <Button
                variant="outlined"
                onClick={async () => {
                  if (knowledgeSpaceName === '') {
                    message.error('please input the name')
                    return
                  }
                  if (owner === '') {
                    message.error('please input the owner')
                    return
                  }
                  if (description === '') {
                    message.error('please input the description')
                    return
                  }
                  const data = await sendSpacePostRequest(
                    `/knowledge/space/add`,
                    {
                      name: knowledgeSpaceName,
                      vector_type: 'Chroma',
                      owner,
                      desc: description
                    }
                  )
                  if (data.success) {
                    message.success('success')
                    setActiveStep(1)
                    const data = await sendSpacePostRequest(
                      '/knowledge/space/list',
                      {}
                    )
                    if (data.success) {
                      setKnowledgeSpaceList(data.data)
                    }
                  } else {
                    message.error(data.err_msg || 'failed')
                  }
                }}
              >
                Next
              </Button>
            </>
          ) : activeStep === 1 ? (
            <>
              <Box sx={{ margin: '30px auto' }}>
                {documentTypeList.map((item: any) => (
                  <Sheet
                    key={item.type}
                    sx={{
                      boxSizing: 'border-box',
                      height: '80px',
                      padding: '12px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      border: '1px solid gray',
                      borderRadius: '6px',
                      marginBottom: '20px',
                      cursor: 'pointer'
                    }}
                    onClick={() => {
                      setDocumentType(item.type)
                      setActiveStep(2)
                    }}
                  >
                    <Sheet sx={{ fontSize: '20px', fontWeight: 'bold' }}>
                      {item.title}
                    </Sheet>
                    <Sheet>{item.subTitle}</Sheet>
                  </Sheet>
                ))}
              </Box>
            </>
          ) : (
            <>
              <Box sx={{ margin: '30px auto' }}>
                Name:
                <Input
                  placeholder="Please input the name"
                  onChange={(e: any) => setDocumentName(e.target.value)}
                  sx={{ marginBottom: '20px' }}
                />
                {documentType === 'webPage' ? (
                  <>
                    Web Page URL:
                    <Input
                      placeholder="Please input the Web Page URL"
                      onChange={(e: any) => setWebPageUrl(e.target.value)}
                    />
                  </>
                ) : documentType === 'file' ? (
                  <>
                    <Dragger {...props}>
                      <p className="ant-upload-drag-icon">
                        <InboxOutlined />
                      </p>
                      <p
                        style={{ color: 'rgb(22, 108, 255)', fontSize: '20px' }}
                      >
                        Select or Drop file
                      </p>
                      <p
                        className="ant-upload-hint"
                        style={{ color: 'rgb(22, 108, 255)' }}
                      >
                        PDF, PowerPoint, Excel, Word, Text, Markdown,
                      </p>
                    </Dragger>
                  </>
                ) : (
                  <>
                    Text Source(Optional):
                    <Input
                      placeholder="Please input the text source"
                      onChange={(e: any) => setTextSource(e.target.value)}
                      sx={{ marginBottom: '20px' }}
                    />
                    Text:
                    <Textarea
                      onChange={(e: any) => setText(e.target.value)}
                      minRows={4}
                      sx={{ marginBottom: '20px' }}
                    />
                  </>
                )}
                <Typography
                  component="label"
                  sx={{
                    marginTop: '20px'
                  }}
                  endDecorator={
                    <Switch
                      checked={synchChecked}
                      onChange={(event: any) =>
                        setSynchChecked(event.target.checked)
                      }
                    />
                  }
                >
                  Synch:
                </Typography>
              </Box>
              <Stack
                direction="row"
                justifyContent="flex-start"
                alignItems="center"
                sx={{ marginBottom: '20px' }}
              >
                <Button
                  variant="outlined"
                  sx={{ marginRight: '20px' }}
                  onClick={() => setActiveStep(1)}
                >
                  {'< Back'}
                </Button>
                <Button
                  variant="outlined"
                  onClick={async () => {
                    if (documentName === '') {
                      message.error('Please input the name')
                      return
                    }
                    if (documentType === 'webPage') {
                      if (webPageUrl === '') {
                        message.error('Please input the Web Page URL')
                        return
                      }
                      const data = await sendSpacePostRequest(
                        `/knowledge/${knowledgeSpaceName}/document/add`,
                        {
                          doc_name: documentName,
                          content: webPageUrl,
                          doc_type: 'URL'
                        }
                      )
                      if (data.success) {
                        message.success('success')
                        setIsAddKnowledgeSpaceModalShow(false)
                        synchChecked &&
                          sendSpacePostRequest(
                            `/knowledge/${knowledgeSpaceName}/document/sync`,
                            {
                              doc_ids: [data.data]
                            }
                          )
                      } else {
                        message.error(data.err_msg || 'failed')
                      }
                    } else if (documentType === 'file') {
                      if (!originFileObj) {
                        message.error('Please select a file')
                        return
                      }
                      const formData = new FormData()
                      formData.append('doc_name', documentName)
                      formData.append('doc_file', originFileObj)
                      formData.append('doc_type', 'DOCUMENT')

                      const data = await sendSpaceUploadPostRequest(
                        `/knowledge/${knowledgeSpaceName}/document/upload`,
                        formData
                      )
                      if (data.success) {
                        message.success('success')
                        setIsAddKnowledgeSpaceModalShow(false)
                        synchChecked &&
                          sendSpacePostRequest(
                            `/knowledge/${knowledgeSpaceName}/document/sync`,
                            {
                              doc_ids: [data.data]
                            }
                          )
                      } else {
                        message.error(data.err_msg || 'failed')
                      }
                    } else {
                      if (text === '') {
                        message.error('Please input the text')
                        return
                      }
                      const data = await sendSpacePostRequest(
                        `/knowledge/${knowledgeSpaceName}/document/add`,
                        {
                          doc_name: documentName,
                          source: textSource,
                          content: text,
                          doc_type: 'TEXT'
                        }
                      )
                      if (data.success) {
                        message.success('success')
                        setIsAddKnowledgeSpaceModalShow(false)
                        synchChecked &&
                          sendSpacePostRequest(
                            `/knowledge/${knowledgeSpaceName}/document/sync`,
                            {
                              doc_ids: [data.data]
                            }
                          )
                      } else {
                        message.error(data.err_msg || 'failed')
                      }
                    }
                  }}
                >
                  Finish
                </Button>
              </Stack>
            </>
          )}
        </Sheet>
      </Modal>
    </Box>
  )
}

export default Index
