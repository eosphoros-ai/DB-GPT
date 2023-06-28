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
import { message } from 'antd'

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

const Documents = () => {
  const router = useRouter()
  const spaceName = useSearchParams().get('name')
  const [isAddDocumentModalShow, setIsAddDocumentModalShow] =
    useState<boolean>(false)
  const [activeStep, setActiveStep] = useState<number>(0)
  const [documents, setDocuments] = useState<any>([])
  const [webPageUrl, setWebPageUrl] = useState<string>('')
  const [documentName, setDocumentName] = useState<string>('')
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
      <Table sx={{ '& thead th:nth-child(1)': { width: '40%' } }}>
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
              <td><Chip color={
                (function(){
                  switch(row.status) {
                    case 'TODO':
                      return 'neutral';
                    case 'RUNNING':
                      return 'primary';
                    case 'FINISHED':
                      return 'success';
                    case 'FAILED':
                      return 'danger';
                  }
                })()
              }>{row.status}</Chip></td>
              <td>
                {
                  <>
                    <Button
                      variant="outlined"
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
                      if (item.type === 'webPage') {
                        setActiveStep(1)
                      }
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
                <Input
                  placeholder="Please input the Web Page URL"
                  onChange={(e: any) => setWebPageUrl(e.target.value)}
                />
              </Box>
              <Button
                onClick={async () => {
                  if (documentName === '') {
                    message.error('Please input the name')
                    return
                  }
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
