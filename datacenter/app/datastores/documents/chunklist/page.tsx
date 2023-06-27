'use client'

import { useSearchParams } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import { Table } from '@/lib/mui'
import { Popover } from 'antd'

const ChunkList = () => {
  const spaceName = useSearchParams().get('spacename')
  const documentId = useSearchParams().get('documentid')
  const [chunkList, setChunkList] = useState<any>([])
  useEffect(() => {
    async function fetchChunks() {
      const res = await fetch(
        `http://localhost:8000/knowledge/${spaceName}/chunk/list`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            document_id: documentId
          })
        }
      )
      const data = await res.json()
      if (data.success) {
        setChunkList(data.data)
      }
    }
    fetchChunks()
  }, [])
  return (
    <div className="p-4">
      <Table sx={{ '& thead th:nth-child(1)': { width: '40%' } }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Content</th>
            <th>Meta Data</th>
          </tr>
        </thead>
        <tbody>
          {chunkList.map((row: any) => (
            <tr key={row.id}>
              <td>{row.doc_name}</td>
              <td>
                {
                  <Popover content={row.content} trigger="hover">
                    {row.content.length > 10
                      ? `${row.content.slice(0, 10)}...`
                      : row.content}
                  </Popover>
                }
              </td>
              <td>
                {
                  <Popover
                    content={JSON.stringify(row.meta_info || '{}', null, 2)}
                    trigger="hover"
                  >
                    {row.meta_info.length > 10
                      ? `${row.meta_info.slice(0, 10)}...`
                      : row.meta_info}
                  </Popover>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}

export default ChunkList
