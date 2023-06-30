'use client'

import { useRouter } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { message, Upload, Popover } from 'antd'
import {
  useColorScheme,
  Modal,
  Button,
  Table,
  Sheet,
  Stack,
  Box,
  Input,
  Textarea,
  Chip,
  Switch,
  Typography,
  styled
} from '@/lib/mui'
import { fetchBaseURL } from '@/app/datastores/constants'

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
  '1.Knowledge Space Config',
  '2.Choose a Datasource type',
  '3.Setup the Datasource'
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
      const res = await fetch(`${fetchBaseURL}/knowledge/space/list`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      })
      const data = await res.json()
      if (data.success) {
        setKnowledgeSpaceList(data.data)
      }
    }
    fetchData()
  }, [])
  return (
    <>
      <Sheet
        sx={{
          display: 'flex',
          justifyContent: 'space-between'
        }}
        className="p-4"
      >
        <Sheet
          sx={{
            fontSize: '30px',
            fontWeight: 'bold'
          }}
        >
          Knowledge Spaces
        </Sheet>
        <Button
          onClick={() => setIsAddKnowledgeSpaceModalShow(true)}
          variant="outlined"
        >
          + New Knowledge Space
        </Button>
      </Sheet>
      <div className="page-body p-4">
        {knowledgeSpaceList.length ? (
          <Table
            color="primary"
            variant="plain"
            size="lg"
            sx={{
              '& tbody tr: hover': {
                backgroundColor:
                  mode === 'light' ? 'rgb(246, 246, 246)' : 'rgb(33, 33, 40)'
              },
              '& tbody tr: hover a': {
                textDecoration: 'underline'
              }
            }}
          >
            <thead>
              <tr>
                <th>Name</th>
                <th>Vector</th>
                <th>Owner</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {knowledgeSpaceList.map((row: any) => (
                <tr key={row.id}>
                  <td>
                    {
                      <a
                        style={{ fontWeight: 'bold' }}
                        href="javascript:;"
                        onClick={() =>
                          router.push(`/datastores/documents?name=${row.name}`)
                        }
                      >
                        {row.name}
                      </a>
                    }
                  </td>
                  <td>
                    <Chip variant="solid" color="neutral" sx={{ opacity: 0.5 }}>
                      {row.vector_type}
                    </Chip>
                  </td>
                  <td>
                    <Chip variant="solid" color="neutral" sx={{ opacity: 0.5 }}>
                      {row.owner}
                    </Chip>
                  </td>
                  <td>
                    <Popover content={row.desc} trigger="hover">
                      {row.desc.length > 10
                        ? `${row.desc.slice(0, 10)}...`
                        : row.desc}
                    </Popover>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <></>
        )}
      </div>
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
                    color: activeStep === index ? '#814DDE' : ''
                  }}
                >
                  {item}
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
                />
              </Box>
              <Button
                variant="outlined"
                onClick={async () => {
                  if (knowledgeSpaceName === '') {
                    message.error('please input the name')
                    return
                  }
                  const res = await fetch(
                    `${fetchBaseURL}/knowledge/space/add`,
                    {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json'
                      },
                      body: JSON.stringify({
                        name: knowledgeSpaceName,
                        vector_type: 'Chroma',
                        owner: 'keting',
                        desc: 'test1'
                      })
                    }
                  )
                  const data = await res.json()
                  if (data.success) {
                    message.success('success')
                    setActiveStep(1)
                    const res = await fetch(
                      `${fetchBaseURL}/knowledge/space/list`,
                      {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({})
                      }
                    )
                    const data = await res.json()
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
                    const res = await fetch(
                      `${fetchBaseURL}/knowledge/${knowledgeSpaceName}/document/add`,
                      {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                          doc_name: documentName,
                          content: webPageUrl,
                          doc_type: 'URL'
                        })
                      }
                    )
                    const data = await res.json()
                    if (data.success) {
                      message.success('success')
                      setIsAddKnowledgeSpaceModalShow(false)
                      fetch(
                        `${fetchBaseURL}/knowledge/${knowledgeSpaceName}/document/sync`,
                        {
                          method: 'POST',
                          headers: {
                            'Content-Type': 'application/json'
                          },
                          body: JSON.stringify({
                            doc_ids: [data.data]
                          })
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
                    const res = await fetch(
                      `${fetchBaseURL}/knowledge/${knowledgeSpaceName}/document/upload`,
                      {
                        method: 'POST',
                        body: formData
                      }
                    )
                    const data = await res.json()
                    if (data.success) {
                      message.success('success')
                      setIsAddKnowledgeSpaceModalShow(false)
                      fetch(
                        `${fetchBaseURL}/knowledge/${knowledgeSpaceName}/document/sync`,
                        {
                          method: 'POST',
                          headers: {
                            'Content-Type': 'application/json'
                          },
                          body: JSON.stringify({
                            doc_ids: [data.data]
                          })
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
                    const res = await fetch(
                      `${fetchBaseURL}/knowledge/${knowledgeSpaceName}/document/add`,
                      {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                          doc_name: documentName,
                          source: textSource,
                          content: text,
                          doc_type: 'TEXT'
                        })
                      }
                    )
                    const data = await res.json()
                    if (data.success) {
                      message.success('success')
                      setIsAddKnowledgeSpaceModalShow(false)
                      fetch(
                        `${fetchBaseURL}/knowledge/${knowledgeSpaceName}/document/sync`,
                        {
                          method: 'POST',
                          headers: {
                            'Content-Type': 'application/json'
                          },
                          body: JSON.stringify({
                            doc_ids: [data.data]
                          })
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
            </>
          )}
        </Sheet>
      </Modal>
    </>
  )
}

export default Index
