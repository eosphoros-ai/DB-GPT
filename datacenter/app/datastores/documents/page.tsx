'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import {
  useColorScheme,
  Button,
  Table,
  Sheet,
  Modal,
  Box,
  Stack,
  Input,
  Textarea,
  Chip,
  Switch,
  Typography,
  Breadcrumbs,
  Link,
  styled
} from '@/lib/mui'
import moment from 'moment'
import { InboxOutlined } from '@ant-design/icons'
import CheckCircleOutlinedIcon from '@mui/icons-material/CheckCircleOutlined'
import CachedIcon from '@mui/icons-material/Cached'
import type { UploadProps } from 'antd'
import { Upload, Pagination, Popover, message } from 'antd'
import {
  sendSpacePostRequest,
  sendSpaceUploadPostRequest
} from '@/utils/request'

const { Dragger } = Upload
const Item = styled(Sheet)(({ theme }) => ({
  width: '50%',
  backgroundColor:
    theme.palette.mode === 'dark' ? theme.palette.background.level1 : '#fff',
  ...theme.typography.body2,
  padding: theme.spacing(1),
  textAlign: 'center',
  borderRadius: 4,
  color: theme.vars.palette.text.secondary
}))
const stepsOfAddingDocument = [
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
const page_size = 20

const Documents = () => {
  const router = useRouter()
  const spaceName = useSearchParams().get('name')
  const { mode } = useColorScheme()
  const [isAddDocumentModalShow, setIsAddDocumentModalShow] =
    useState<boolean>(false)
  const [activeStep, setActiveStep] = useState<number>(0)
  const [documentType, setDocumentType] = useState<string>('')
  const [documents, setDocuments] = useState<any>([])
  const [webPageUrl, setWebPageUrl] = useState<string>('')
  const [documentName, setDocumentName] = useState<any>('')
  const [textSource, setTextSource] = useState<string>('')
  const [text, setText] = useState<string>('')
  const [originFileObj, setOriginFileObj] = useState<any>(null)
  const [total, setTotal] = useState<number>(0)
  const [current, setCurrent] = useState<number>(0)
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
    async function fetchDocuments() {
      const data = await sendSpacePostRequest(
        `/knowledge/${spaceName}/document/list`,
        {
          page: 1,
          page_size
        }
      )
      if (data.success) {
        setDocuments(data.data.data)
        setTotal(data.data.total)
        setCurrent(data.data.page)
      }
    }
    fetchDocuments()
  }, [])
  return (
    <div className="p-4">
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ marginBottom: '20px' }}
      >
        <Breadcrumbs aria-label="breadcrumbs">
          <Link
            onClick={() => {
              router.push('/datastores')
            }}
            key="Knowledge Space"
            underline="hover"
            color="neutral"
            fontSize="inherit"
          >
            Knowledge Space
          </Link>
          <Typography fontSize="inherit">Documents</Typography>
        </Breadcrumbs>
        <Button
          variant="outlined"
          onClick={() => setIsAddDocumentModalShow(true)}
        >
          + Add Datasource
        </Button>
      </Stack>
      {documents.length ? (
        <>
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
                <th>Type</th>
                <th>Size</th>
                <th>Last Synch</th>
                <th>Status</th>
                <th>Result</th>
                <th>Operation</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((row: any) => (
                <tr key={row.id}>
                  <td>{row.doc_name}</td>
                  <td>
                    <Chip variant="solid" color="neutral" sx={{ opacity: 0.5 }}>
                      {row.doc_type}
                    </Chip>
                  </td>
                  <td>{row.chunk_size} chunks</td>
                  <td>{moment(row.last_sync).format('YYYY-MM-DD HH:MM:SS')}</td>
                  <td>
                    <Chip
                      sx={{ opacity: 0.5 }}
                      variant="solid"
                      color={(function () {
                        switch (row.status) {
                          case 'TODO':
                            return 'neutral'
                          case 'RUNNING':
                            return 'primary'
                          case 'FINISHED':
                            return 'success'
                          case 'FAILED':
                            return 'danger'
                        }
                      })()}
                    >
                      {row.status}
                    </Chip>
                  </td>
                  <td>
                    {(function () {
                      if (row.status === 'TODO' || row.status === 'RUNNING') {
                        return ''
                      } else if (row.status === 'FINISHED') {
                        return (
                          <Popover content={row.result} trigger="hover">
                            <Chip
                              variant="solid"
                              color="success"
                              sx={{ opacity: 0.5 }}
                            >
                              SUCCESS
                            </Chip>
                          </Popover>
                        )
                      } else {
                        return (
                          <Popover content={row.result} trigger="hover">
                            <Chip
                              variant="solid"
                              color="danger"
                              sx={{ opacity: 0.5 }}
                            >
                              FAILED
                            </Chip>
                          </Popover>
                        )
                      }
                    })()}
                  </td>
                  <td>
                    {
                      <>
                        <Button
                          variant="outlined"
                          size="sm"
                          sx={{
                            marginRight: '20px'
                          }}
                          onClick={async () => {
                            const data = await sendSpacePostRequest(
                              `/knowledge/${spaceName}/document/sync`,
                              {
                                doc_ids: [row.id]
                              }
                            )
                            if (data.success) {
                              message.success('success')
                            } else {
                              message.error(data.err_msg || 'failed')
                            }
                          }}
                        >
                          Synch
                          <CachedIcon />
                        </Button>
                        <Button
                          variant="outlined"
                          size="sm"
                          onClick={() => {
                            router.push(
                              `/datastores/documents/chunklist?spacename=${spaceName}&documentid=${row.id}`
                            )
                          }}
                        >
                          Details
                        </Button>
                      </>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Stack
            direction="row"
            justifyContent="flex-end"
            sx={{
              marginTop: '20px'
            }}
          >
            <Pagination
              defaultPageSize={20}
              showSizeChanger={false}
              current={current}
              total={total}
              onChange={async (page) => {
                const data = await sendSpacePostRequest(
                  `/knowledge/${spaceName}/document/list`,
                  {
                    page,
                    page_size
                  }
                )
                if (data.success) {
                  setDocuments(data.data.data)
                  setTotal(data.data.total)
                  setCurrent(data.data.page)
                }
              }}
              hideOnSinglePage
            />
          </Stack>
        </>
      ) : (
        <></>
      )}
      <Modal
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          'z-index': 1000
        }}
        open={isAddDocumentModalShow}
        onClose={() => setIsAddDocumentModalShow(false)}
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
              {stepsOfAddingDocument.map((item: any, index: number) => (
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
                      setActiveStep(1)
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
                  onClick={() => setActiveStep(0)}
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
                        `/knowledge/${spaceName}/document/add`,
                        {
                          doc_name: documentName,
                          content: webPageUrl,
                          doc_type: 'URL'
                        }
                      )
                      data.success &&
                        synchChecked &&
                        sendSpacePostRequest(
                          `/knowledge/${spaceName}/document/sync`,
                          {
                            doc_ids: [data.data]
                          }
                        )
                      if (data.success) {
                        message.success('success')
                        setIsAddDocumentModalShow(false)
                        const data = await sendSpacePostRequest(
                          `/knowledge/${spaceName}/document/list`,
                          {
                            page: current,
                            page_size
                          }
                        )
                        if (data.success) {
                          setDocuments(data.data.data)
                          setTotal(data.data.total)
                          setCurrent(data.data.page)
                        }
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
                        `/knowledge/${spaceName}/document/upload`,
                        formData
                      )
                      data.success &&
                        synchChecked &&
                        sendSpacePostRequest(
                          `/knowledge/${spaceName}/document/sync`,
                          {
                            doc_ids: [data.data]
                          }
                        )
                      if (data.success) {
                        message.success('success')
                        setIsAddDocumentModalShow(false)
                        const data = await sendSpacePostRequest(
                          `/knowledge/${spaceName}/document/list`,
                          {
                            page: current,
                            page_size
                          }
                        )
                        if (data.success) {
                          setDocuments(data.data.data)
                          setTotal(data.data.total)
                          setCurrent(data.data.page)
                        }
                      } else {
                        message.error(data.err_msg || 'failed')
                      }
                    } else {
                      if (text === '') {
                        message.error('Please input the text')
                        return
                      }
                      const data = await sendSpacePostRequest(
                        `/knowledge/${spaceName}/document/add`,
                        {
                          doc_name: documentName,
                          source: textSource,
                          content: text,
                          doc_type: 'TEXT'
                        }
                      )
                      data.success &&
                        synchChecked &&
                        sendSpacePostRequest(
                          `/knowledge/${spaceName}/document/sync`,
                          {
                            doc_ids: [data.data]
                          }
                        )
                      if (data.success) {
                        message.success('success')
                        setIsAddDocumentModalShow(false)
                        const data = await sendSpacePostRequest(
                          `/knowledge/${spaceName}/document/list`,
                          {
                            page: current,
                            page_size
                          }
                        )
                        if (data.success) {
                          setDocuments(data.data.data)
                          setTotal(data.data.total)
                          setCurrent(data.data.page)
                        }
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
    </div>
  )
}

export default Documents
