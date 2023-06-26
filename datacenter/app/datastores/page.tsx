'use client'

import Router from 'next/router'
import type { ProFormInstance } from '@ant-design/pro-components';
import React, { useState, useRef, useEffect } from 'react'
import {
  ProCard,
  ProForm,
  ProFormCheckbox,
  ProFormDatePicker,
  ProFormDateRangePicker,
  ProFormSelect,
  ProFormText,
  ProFormTextArea,
  StepsForm
} from '@ant-design/pro-components'
import { Button, Modal, Table, message } from 'antd'

const Index = () => {
  const formRef = useRef<ProFormInstance>();
  const [knowledgeSpaceList, setKnowledgeSpaceList] = useState<any>([]);
  const [isAddKnowledgeSpaceModalShow, setIsAddKnowledgeSpaceModalShow] =
    useState<boolean>(false);
  const [knowledgeSpaceName, setKnowledgeSpaceName] = useState<string>('');
  const [webPageUrl, setWebPageUrl] = useState<string>('');
  useEffect(() => {
    async function fetchData() {
      const res = await fetch('http://localhost:8000/knowledge/space/list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (data.success) {
        setKnowledgeSpaceList(data.data);
      }
    }
    fetchData();
  }, []);
  return (
    <>
      <div className="page-header p-4">
        <div className="page-header-title">Knowledge Spaces</div>
        <Button onClick={() => setIsAddKnowledgeSpaceModalShow(true)} type='default'>
          + New Knowledge Space
        </Button>
      </div>
      <div className="page-body p-4">
        <Table
          columns={[
            {
              title: 'Name',
              dataIndex: 'name',
              key: 'name',
              align: 'center',
              render: (text: string) => {
                return <a href='javascript:;' onClick={() => Router.push(`/datastores/documents?name=${text}`)}>{text}</a>
              }
            },
            {
              title: 'Provider',
              dataIndex: 'vector_type',
              key: 'vector_type',
              align: 'center',
            },
            {
              title: 'Owner',
              dataIndex: 'owner',
              key: 'owner',
              align: 'center',
            },
          ]}
          dataSource={knowledgeSpaceList}
        />
      </div>
      <Modal
        title="Add Knowledge Space"
        footer={null}
        width={900}
        open={isAddKnowledgeSpaceModalShow}
        onOk={() => console.log('ok')}
        onCancel={() => setIsAddKnowledgeSpaceModalShow(false)}
      >
        <ProCard>
          <StepsForm<{
            name: string
          }>
            formRef={formRef}
            onFinish={async () => {
              message.success('success')
            }}
            formProps={{
              validateMessages: {
                required: 'This is required'
              }
            }}
            submitter={{
              render: (props) => {
                if (props.step === 0) {
                  return (
                    <Button type="default" onClick={async () => {
                      if (knowledgeSpaceName === '') {
                        props.onSubmit?.()
                      } else {
                        const res = await fetch('http://localhost:8000/knowledge/space/add', {
                          method: 'POST',
                          headers: {
                          'Content-Type': 'application/json',
                          },
                          body: JSON.stringify({
                            name: knowledgeSpaceName,
                            vector_type: "Chroma",
                            owner: "keting",
                            desc: "test1"
                          }),
                        });
                        const data = await res.json();
                        if (data.success) {
                          props.onSubmit?.();
                          message.success('success');
                          const res = await fetch('http://localhost:8000/knowledge/space/list', {
                            method: 'POST',
                            headers: {
                              'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({}),
                          });
                          const data = await res.json();
                          if (data.success) {
                            setKnowledgeSpaceList(data.data);
                          }
                        } else {
                          message.error(data.err_msg || 'failed');
                        }
                      }
                    }}>
                      Next {'>'}
                    </Button>
                  );
                } else if (props.step === 1) {
                  return (
                    <Button type="default" onClick={() => props.onSubmit?.()}>
                      Web Page {'>'}
                    </Button>
                  );
                }
                
                return [
                  <Button key="gotoTwo" onClick={() => props.onPre?.()}>
                    Previous {'<'} 
                  </Button>,
                  <Button
                    type="default"
                    key="goToTree"
                    onClick={async () => {
                      props.onSubmit?.();
                      const res = await fetch(`http://localhost:8000/knowledge/${knowledgeSpaceName}/document/add`, {
                        method: 'POST',
                        headers: {
                        'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                          doc_name: webPageUrl,
                          doc_type: 'URL'
                        }),
                      });
                      const data = await res.json();
                      if (data.success) {
                        props.onSubmit?.();
                        message.success('success');
                        setIsAddKnowledgeSpaceModalShow(false);
                      } else {
                        message.error(data.err_msg || 'failed');
                      }
                    }}
                  >
                    Finish
                  </Button>,
                ];
              },
            }}
          >
            <StepsForm.StepForm<{
              name: string
            }>
              name="base"
              title="Knowledge Space Configuration"
              onFinish={async () => {
                console.log(formRef.current?.getFieldsValue())
                return true
              }}
            >
              <ProFormText
                name="name"
                label="Knowledge Space Name"
                width="lg"
                placeholder="Please input the name"
                rules={[{ required: true }]}
                onChange={(e: any) => setKnowledgeSpaceName(e.target.value)}
              />
            </StepsForm.StepForm>
            <StepsForm.StepForm<{
              checkbox: string
            }>
              name="checkbox"
              title="Choose a Datasource type"
              onFinish={async () => {
                console.log(formRef.current?.getFieldsValue())
                return true
              }}
            >
            </StepsForm.StepForm>
            <StepsForm.StepForm
              name="time"
              title="Setup the Datasource"
            >
              <ProFormText
                name="webPageUrl"
                label="Web Page URL"
                width="lg"
                placeholder="Please input the Web Page URL"
                rules={[{ required: true }]}
                onChange={(e: any) => setWebPageUrl(e.target.value)}
              />
            </StepsForm.StepForm>
          </StepsForm>
        </ProCard>
      </Modal>
      <style jsx>{`
        .page-header {
          display: flex;
          justify-content: space-between;
          .page-header-title {
            font-size: 30px;
            font-weight: bold
          }
        }
        .datasource-type-wrap {
          height: 100px;
          line-height: 100px;
          border: 1px solid black;
          border-radius: 20px;
          margin-bottom: 20px;
          cursor: pointer;
        }
      `}</style>
    </>
  )
}

export default Index
