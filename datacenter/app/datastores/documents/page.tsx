'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import {
  Button,
  Table,
  Sheet,
  Modal,
  Box,
  Stack,
  Input,
  Chip,
  styled
} from '@/lib/mui'
import moment from 'moment'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { Upload, message } from 'antd'

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
    subTitle: 'Paste some text'
  },
  {
    type: 'webPage',
    title: 'Web Page',
    subTitle: 'Crawl text from a web page'
  },
  {
    type: 'file',
    title: 'File',
    subTitle: 'It can be: PDF, CSV, JSON, Text, PowerPoint, Word, Excel'
  }
]

const Documents = () => {
  const router = useRouter()
  const spaceName = useSearchParams().get('name')
  const [isAddDocumentModalShow, setIsAddDocumentModalShow] =
    useState<boolean>(false)
  const [activeStep, setActiveStep] = useState<number>(0)
  const [documentType, setDocumentType] = useState<string>('')
  const [documents, setDocuments] = useState<any>([])
  const [webPageUrl, setWebPageUrl] = useState<string>('')
  const [documentName, setDocumentName] = useState<any>('')
  const [originFileObj, setOriginFileObj] = useState<any>(null)
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
      const res = await fetch(
        `http://localhost:8000/knowledge/${spaceName}/document/list`,
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
        setDocuments(data.data)
      }
    }
    fetchDocuments()
  }, [])
  return (
    <div className="p-4">
      <Sheet
        sx={{
          display: 'flex',
          flexDirection: 'row-reverse'
        }}
      >
        <Button
          variant="outlined"
          onClick={() => setIsAddDocumentModalShow(true)}
        >
          + Add Datasource
        </Button>
      </Sheet>
      <Table color="neutral" stripe="odd" variant="outlined">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Size</th>
            <th>Last Synch</th>
            <th>Status</th>
            <th>Operation</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((row: any) => (
            <tr key={row.id}>
              <td>{row.doc_name}</td>
              <td>{row.doc_type}</td>
              <td>{row.chunk_size}</td>
              <td>{moment(row.last_sync).format('YYYY-MM-DD HH:MM:SS')}</td>
              <td>
                <Chip
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
                {
                  <>
                    <Button
                      variant="outlined"
                      size="sm"
                      onClick={async () => {
                        const res = await fetch(
                          `http://localhost:8000/knowledge/${spaceName}/document/sync`,
                          {
                            method: 'POST',
                            headers: {
                              'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                              doc_ids: [row.id]
                            })
                          }
                        )
                        const data = await res.json()
                        if (data.success) {
                          message.success('success')
                        } else {
                          message.error(data.err_msg || 'failed')
                        }
                      }}
                    >
                      Synch
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
                      Detail of Chunks
                    </Button>
                  </>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
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
                  sx={{ fontWeight: activeStep === index ? 'bold' : '' }}
                >
                  {item}
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
                Web Page URL:
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
                  <></>
                )}
              </Box>
              <Button
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
                      `http://localhost:8000/knowledge/${spaceName}/document/add`,
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
                      setIsAddDocumentModalShow(false)
                      const res = await fetch(
                        `http://localhost:8000/knowledge/${spaceName}/document/list`,
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
                        setDocuments(data.data)
                      }
                    } else {
                      message.error(data.err_msg || 'failed')
                    }
                  } else if (documentType === 'file') {
                    if (!originFileObj) {
                      message.error('Please select a file')
                      return
                    }
                    const formData = new FormData();
                    formData.append('doc_name', documentName);
                    formData.append('doc_file', originFileObj);
                    formData.append('doc_type', 'DOCUMENT');
                    const res = await fetch(
                      `http://localhost:8000/knowledge/${spaceName}/document/upload`,
                      {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW'
                        },
                        body: formData
                      }
                    )
                    const data = await res.json()
                    if (data.success) {
                      message.success('success')
                      setIsAddDocumentModalShow(false)
                      const res = await fetch(
                        `http://localhost:8000/knowledge/${spaceName}/document/list`,
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
                        setDocuments(data.data)
                      }
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
    </div>
  )
}

export default Documents
