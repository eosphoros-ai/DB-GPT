"use client";

import Router from 'next/router'
import { withRouter } from 'next/router'
import React, { useState, useEffect } from 'react';
import { Table, Button } from 'antd';
import moment from 'moment';

const Documents = ({ router }) => {
    const [documents, setDocuments] = useState<any>([]);
    useEffect(() => {
        async function fetchDocuments() {
            const res = await fetch(`http://localhost:8000/knowledge/${router.query.name}/document/list`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({}),
            });
            const data = await res.json();
            if (data.success) {
                setDocuments(data.data);
            }
        }
        fetchDocuments();
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
                        title: 'Type',
                        dataIndex: 'doc_type',
                        key: 'doc_type',
                        align: 'center',
                    },
                    {
                        title: 'Size',
                        dataIndex: 'chunk_size',
                        key: 'chunk_size',
                        align: 'center',
                    },
                    {
                        title: 'Last Synch',
                        dataIndex: 'last_sync',
                        key: 'last_sync',
                        align: 'center',
                        render: (text: string) => moment(text).format('YYYY-MM-DD HH:MM:SS')
                    },
                    {
                        title: 'Status',
                        dataIndex: 'status',
                        key: 'status',
                        align: 'center',
                    },
                    {
                        title: 'Operation',
                        dataIndex: 'operation',
                        key: 'operation',
                        align: 'center',
                        render: (_: any, label: any) => {
                            return (
                                <Button onClick={() => {
                                    Router.push(`/datastores/documents/chunklist?spacename=${router.query.name}&documentid=${label.id}`)
                                }}>Detail of Chunks</Button>
                            )
                        }
                    },
                ]}
                dataSource={documents}
            />
        </div>
    )
}

export default withRouter(Documents);