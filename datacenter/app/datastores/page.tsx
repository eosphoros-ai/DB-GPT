'use client'

import { useRouter } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import { message } from 'antd'
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
  const [knowledgeSpaceList, setKnowledgeSpaceList] = useState<any>([])
  const [isAddKnowledgeSpaceModalShow, setIsAddKnowledgeSpaceModalShow] =
    useState<boolean>(false)
  const [knowledgeSpaceName, setKnowledgeSpaceName] = useState<string>('')
  const [webPageUrl, setWebPageUrl] = useState<string>('')
  const [documentName, setDocumentName] = useState<string>('')
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
      <Sheet sx={{
        display: "flex",
        justifyContent: "space-between"
      }} className="p-4">
        <Sheet sx={{
          fontSize: '30px',
          fontWeight: 'bold'
        }}>Knowledge Spaces</Sheet>
        <Button
          onClick={() => setIsAddKnowledgeSpaceModalShow(true)}
          variant="outlined"
        >
          + New Knowledge Space
        </Button>
      </Sheet>
      <div className="page-body p-4">
        <Table sx={{ '& thead th:nth-child(1)': { width: '40%' } }}>
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
                      if (item.type === 'webPage') {
                        setActiveStep(2);
                      }
                    }}
                  >
                    <Sheet sx={{ fontSize: '20px', fontWeight: 'bold' }}>{item.title}</Sheet>
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
                  sx={{ marginBottom: '20px'}}
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
                    message.error('Please input the name');
                    return;
                  }
                  if (webPageUrl === '') {
                    message.error('Please input the Web Page URL');
                    return;
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
