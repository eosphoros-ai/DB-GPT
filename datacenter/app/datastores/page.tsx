'use client'

import { useRouter } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { message, Upload } from 'antd'
import {
  Modal,
  Button,
  Table,
  Sheet,
  Stack,
  Box,
  Input,
  styled
} from '@/lib/mui'

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
  'Knowledge Space Configuration',
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

const Index = () => {
  const router = useRouter()
  const [activeStep, setActiveStep] = useState<number>(0)
  const [documentType, setDocumentType] = useState<string>('')
  const [knowledgeSpaceList, setKnowledgeSpaceList] = useState<any>([])
  const [isAddKnowledgeSpaceModalShow, setIsAddKnowledgeSpaceModalShow] =
    useState<boolean>(false)
  const [knowledgeSpaceName, setKnowledgeSpaceName] = useState<string>('')
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
    async function fetchData() {
      const res = await fetch('http://localhost:8000/knowledge/space/list', {
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
        <Table color="neutral" stripe="odd" variant="outlined">
          <thead>
            <tr>
              <th>Name</th>
              <th>Provider</th>
              <th>Owner</th>
            </tr>
          </thead>
          <tbody>
            {knowledgeSpaceList.map((row: any) => (
              <tr key={row.id}>
                <td>
                  {
                    <a
                      href="javascript:;"
                      onClick={() =>
                        router.push(`/datastores/documents?name=${row.name}`)
                      }
                    >
                      {row.name}
                    </a>
                  }
                </td>
                <td>{row.vector_type}</td>
                <td>{row.owner}</td>
              </tr>
            ))}
          </tbody>
        </Table>
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
                    'http://localhost:8000/knowledge/space/add',
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
                      'http://localhost:8000/knowledge/space/list',
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
                      `http://localhost:8000/knowledge/${knowledgeSpaceName}/document/add`,
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
                      `http://localhost:8000/knowledge/${knowledgeSpaceName}/document/upload`,
                      {
                        method: 'POST',
                        body: formData
                      }
                    )
                    const data = await res.json()
                    if (data.success) {
                      message.success('success')
                      setIsAddKnowledgeSpaceModalShow(false)
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
