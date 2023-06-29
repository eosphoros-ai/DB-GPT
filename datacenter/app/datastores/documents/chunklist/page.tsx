'use client'

import { useSearchParams } from 'next/navigation'
import React, { useState, useEffect } from 'react'
import { Table, Stack } from '@/lib/mui'
import { Popover, Pagination } from 'antd'
const page_size = 20

const ChunkList = () => {
  const spaceName = useSearchParams().get('spacename')
  const documentId = useSearchParams().get('documentid')
  const [total, setTotal] = useState<number>(0)
  const [current, setCurrent] = useState<number>(0)
  const [chunkList, setChunkList] = useState<any>([])
  useEffect(() => {
    async function fetchChunks() {
      const res = await fetch(
        `http://30.183.154.125:5000/knowledge/${spaceName}/chunk/list`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            document_id: documentId,
            page: 1,
            page_size
          })
        }
      )
      const data = await res.json()
      if (data.success) {
        setChunkList(data.data.data)
        setTotal(data.data.total)
        setCurrent(data.data.page)
      }
    }
    fetchChunks()
  }, [])
  return (
    <div className="p-4">
      {chunkList.length ? (
        <>
          <Table color="neutral" stripe="odd" variant="outlined">
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
          <Stack direction="row" justifyContent="flex-end" sx={{
            marginTop: '20px'
          }}>
            <Pagination
              defaultPageSize={20}
              showSizeChanger={false}
              current={current}
              total={total}
              onChange={async (page) => {
                const res = await fetch(
                  `http://30.183.154.125:5000/knowledge/${spaceName}/chunk/list`,
                  {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                      document_id: documentId,
                      page,
                      page_size
                    })
                  }
                )
                const data = await res.json()
                if (data.success) {
                  setChunkList(data.data.data)
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
    </div>
  )
}

export default ChunkList
