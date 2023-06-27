'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import { Button, Table } from '@/lib/mui'
import moment from 'moment'

const Documents = () => {
  const router = useRouter()
  const spaceName = useSearchParams().get('name')
  const [documents, setDocuments] = useState<any>([])
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
              <td>{row.status}</td>
              <td>
                {
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
                }
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}

export default Documents
