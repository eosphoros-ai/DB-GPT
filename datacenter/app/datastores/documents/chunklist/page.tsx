"use client";

import { useSearchParams } from 'next/navigation'
import React, { useState, useEffect } from 'react';
import { Table, Popover } from 'antd';
import moment from 'moment';

const ChunkList = () => {
    const spaceName = useSearchParams().get('spacename');
    const documentId = useSearchParams().get('documentid');
    const [chunkList, setChunkList] = useState<any>([]);
    useEffect(() => {
        async function fetchChunks() {
            const res = await fetch(`http://localhost:8000/knowledge/${spaceName}/chunk/list`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_id: documentId
                }),
            });
            const data = await res.json();
            if (data.success) {
                setChunkList(data.data);
            }
        }
        fetchChunks();
    }, []);
    return (
        <div className='p-4'>
            <Table
                columns={[
                    {
                        title: 'Name',
                        dataIndex: 'doc_name',
                        key: 'doc_name',
                        align: 'center',
                    },
                    {
                        title: 'Content',
                        dataIndex: 'content',
                        key: 'content',
                        align: 'center',
                        render: (text: string, label: any) => {
                            return <Popover content={text} trigger="hover">{text.length < 10 ? `${text.slice(0, 10)}...` : text}</Popover>;
                        }
                    },
                    {
                        title: 'Meta Data',
                        dataIndex: 'meta_info',
                        key: 'meta_info',
                        align: 'center',
                        render: (text: string, label: any) => {
                            return <Popover content={JSON.stringify(text || '{}', null, 2)} trigger="hover">{text.length < 10 ? `${text.slice(0, 10)}...` : text}</Popover>;
                        }
                    },
                ]}
                dataSource={chunkList}
            />
        </div>
    )
}

export default ChunkList;