import React, { useEffect, useMemo, useState } from 'react';
import {
  Divider,
  Button,
  Space,
  Table,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Upload,
  message,
  Tooltip,
  Popconfirm,
  Segmented,
  ConfigProvider,
  Statistic,
  Badge,
} from 'antd';
import type { TableProps } from 'antd';
import {
  getTestAuth,
  apiInterceptors,
  getEvaluations,
  getDataSets,
  uploadDataSets,
  delDataSet,
  downloadDataSet,
  createEvaluations,
  getSpaceList,
  getAppList,
  getStorageTypes,
  uploadDataSetsContent,
  uploadDataSetsFile,
  delEvaluation,
  showEvaluation,
  getMetrics,
  updateEvaluations,
  downloadEvaluation,
} from '@/client/api';
type Props = {};
import { useRequest } from 'ahooks';
import { InfoCircleOutlined, UploadOutlined } from '@ant-design/icons';
const { TextArea } = Input;
const { useWatch } = Form;
interface DataSetItemType {
  code: string;
  name: string;
  file_type: string;
  storage_type: string;
  storage_position: string;
  datasets_count: string;
  have_answer: boolean;
  members: string;
  user_name: string;
  user_id: string;
  sys_code: string;
  gmt_create: string;
  gmt_modified: string;
}
interface EvaluationItemType {
  evaluate_code: string;
  scene_key: string;
  scene_value: string;
  datasets: string;
  evaluate_metrics: string;
  context: Object;
  user_name: string;
  user_id: string;
  sys_code: string;
  parallel_num: string;
  state: string;
  result: string;
  average_score: string;
  log_info: string;
  gmt_create: string;
  gmt_modified: string;
}
const Evaluation = (props: Props) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDataSetModalOpen, setIsDataSetModalOpen] = useState(false);
  const [evaluationList, setEvaluationList] = useState<EvaluationItemType[]>([]);
  const [evaluationTotal, setEvaluationTotal] = useState<number>(0);
  const [dataSetsTotal, setDataSetsTotal] = useState<number>(0);

  const [sceneValueOptions, setSceneValueOptions] = useState<{ label: string; value: string }[]>();
  const [metricOptions, setMetricOptions] = useState<{ label: string; value: string }[]>();
  const [sceneValueOptionLoading, setSceneValueOptionLoading] = useState(false);
  const [currentTable, setCurrentTable] = useState('evaluations');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isAddDataSet, setIsAddDataSet] = useState(true);
  const [evaluationShowData, setEvaluationShowData] = useState<Record<string, string>[]>([{}]);
  const [storageTypeOptions, setStorageTypeOptions] = useState<{ label: string; value: string }[]>();
  const [dataSetsList, setDataSetsList] = useState<DataSetItemType[]>([]);
  const [currentEvaluationCode, setCurrentEvaluationCode] = useState<string>('');
  const [dataSetModalLoading, setDataSetModalLoading] = useState(false);
  const [evaluationModalLoading, setEvaluationModalLoading] = useState(false);
  const [commonLoading, setCommonLoading] = useState(false);

  const dataSetsOptions = useMemo(() => {
    return dataSetsList?.map((item) => {
      return {
        label: item?.name,
        value: item?.code,
      };
    });
  }, [dataSetsList]);
  const [form] = Form.useForm();
  const [dataSetForm] = Form.useForm();
  //getMetrics
  const { run: runGetMetrics, loading: getMetricsLoading } = useRequest(
    async (params) => {
      const [_, data] = await apiInterceptors(getMetrics(params));
      return data;
    },
    {
      manual: true,
      onSuccess: (data) => {
        console.log(
          data,
          data?.map((i: Record<string, string>) => {
            return { label: i.describe, value: i.name };
          }),
        );
        setMetricOptions(
          data?.map((i: Record<string, string>) => {
            return { label: i.describe, value: i.name };
          }),
        );
      },
    },
  );
  //showEvaluation
  const { run: runShowEvaluation, loading: showEvaluationLoading } = useRequest(
    async (params) => {
      const [_, data] = await apiInterceptors(showEvaluation(params));
      return data;
    },
    {
      manual: true,
      onSuccess: (data) => {
        if (data && data.length) {
          setEvaluationShowData(data);
          setIsModalVisible(true);
        }
      },
    },
  );
  //getStorageTypes
  const { run: runGetStorageTypes } = useRequest(
    async () => {
      const [_, data] = await apiInterceptors(getStorageTypes());
      return data;
    },
    {
      onSuccess: (data) => {
        data &&
          setStorageTypeOptions(
            data.map((i: Record<string, string>[]) => {
              let [k, v] = Object.entries(i)[0];
              return { label: v, value: k };
            }),
          );
      },
    },
  );
  const {
    run: runGetEvaluations,
    loading: getEvaluationsLoading,
    refresh: getEvaluationsRefresh,
  } = useRequest(
    async (page = 1, page_size = 10) => {
      const [_, data] = await apiInterceptors(
        getEvaluations({
          page,
          page_size,
        }),
      );
      return data;
    },
    {
      // manual: true,
      onSuccess: (data) => {
        console.log(data);
        setEvaluationList(data?.items);
        setEvaluationTotal(data?.total_count);
      },
    },
  );
  const {
    run: runGetDataSets,
    loading: getDataSetsLoading,
    refresh: getDataSetsRefresh,
  } = useRequest(
    async (page = 1, page_size = 10) => {
      const [_, data] = await apiInterceptors(
        getDataSets({
          page,
          page_size,
        }),
      );
      return data;
    },
    {
      // manual: true,
      onSuccess: (data) => {
        setDataSetsList(data?.items);
        setDataSetsTotal(data?.total_count);
      },
    },
  );
  //uploadDataSets
  const {
    run: runUploadDataSets,
    loading: uploadDataSetsLoading,
    refresh: uploadDataSetsRefresh,
  } = useRequest(
    async (data) => {
      const [_, res] = await apiInterceptors(
        uploadDataSets({
          ...data,
        }),
      );
      return res;
    },
    {
      manual: true,
      onSuccess: (res) => {
        setEvaluationList(res?.items);
      },
    },
  );

  const columns: TableProps<DataSetItemType>['columns'] = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: '10%',
      fixed: 'left',
    },
    {
      title: '编码',
      dataIndex: 'code',
      key: 'code',
      width: '20%',
      // render: (text) => <a>{text}</a>,
    },
    {
      title: '储存方式',
      dataIndex: 'storage_type',
      key: 'storage_type',
    },
    {
      title: '数据集数量',
      dataIndex: 'datasets_count',
      key: 'datasets_count',
    },

    {
      title: '创建时间',
      dataIndex: 'gmt_create',
      key: 'gmt_create',
    },
    {
      title: '成员',
      dataIndex: 'members',
      key: 'members',
      width: '10%',
      render: (text) => {
        return text?.split(',').map((item: string) => {
          return <Tag key={item}>{item}</Tag>;
        });
      },
    },
    {
      title: '更新时间',
      dataIndex: 'gmt_modified',
      key: 'gmt_modified',
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Popconfirm
            title="确认删除吗"
            onConfirm={async () => {
              const [, , res] = await apiInterceptors(
                delDataSet({
                  code: record?.code,
                }),
              );
              console.log(res);
              if (res?.success == true) {
                message.success('删除成功');
                getDataSetsRefresh();
              }
            }}
          >
            <Button type="link">删除</Button>
          </Popconfirm>
          <Button
            type="link"
            onClick={() => {
              setIsAddDataSet(false);
              setIsDataSetModalOpen(true);
              setCurrentEvaluationCode(record?.code);
              dataSetForm.setFieldsValue({
                dataset_name: record?.name,
                members: record?.members?.split(','),
              });
            }}
          >
            编辑
          </Button>
          <Button
            type="link"
            loading={commonLoading}
            onClick={async () => {
              setCommonLoading(true);
              let response = await downloadDataSet({
                code: record?.code,
              });
              const contentType = response.headers['content-type'];
              if (contentType.includes('application/json')) {
                // 如果是 JSON，解析错误信息
                const reader = new FileReader();
                reader.onload = () => {
                  try {
                    const error = JSON.parse(reader.result as string);
                    message.error(error.err_msg);
                    // 在页面或通知系统中展示错误信息
                  } catch (parseError) {
                    console.error('Failed to parse error response:', parseError);
                  }
                };
                reader.readAsText(response.data as any);
              } else {
                // 从响应头中获取文件名
                const contentDisposition = response.headers['content-disposition'];
                let filename = 'downloaded_file.xlsx';
                if (contentDisposition) {
                  const match = contentDisposition.match(/filename\*?="?(.+)"/);
                  if (match[1]) {
                    filename = decodeURIComponent(match[1]);
                  }
                }

                // 创建 URL 并触发下载
                const url = window.URL.createObjectURL(
                  new Blob([response.data as any], {
                    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                  }),
                );
                console.log(url, response);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url); // 释放内存
              }
              setCommonLoading(false);
            }}
          >
            下载
          </Button>
        </Space>
      ),
    },
  ];
  /* evaluations Columns
   */
  const evaluationsColumns: TableProps<EvaluationItemType>['columns'] = [
    {
      title: '数据集名称',
      dataIndex: 'datasets_name',
      key: 'datasets_name',
      fixed: 'left',
      width: '15%',
      render: (text) => (
        <span
          style={{
            textWrap: 'nowrap',
            maxWidth: '300px',
          }}
        >
          {text}
        </span>
      ),
    },
    {
      title: '测评状态',
      dataIndex: 'state',
      key: 'state',
      render: (text) => {
        return <Badge style={{ textWrap: 'nowrap' }} status={text == 'failed' ? 'error' : 'success'} text={text} />;
      },
    },
    {
      title: '测评编码',
      dataIndex: 'evaluate_code',
      key: 'evaluate_code',
    },
    {
      title: '场景',
      dataIndex: 'scene_key',
      key: 'scene_key',
    },

    {
      title: '测评指标',
      dataIndex: 'evaluate_metrics',
      key: 'evaluate_metrics',
    },
    {
      title: '创建时间',
      dataIndex: 'gmt_create',
      key: 'gmt_create',
    },
    {
      title: '更新时间',
      dataIndex: 'gmt_modified',
      key: 'gmt_modified',
    },
    Table.EXPAND_COLUMN,
    {
      title: (
        <span className="w-[50px]">
          <span className="text-nowrap">详情</span>
          <Tooltip placement="topLeft" title="查看日志与评分">
            <InfoCircleOutlined />
          </Tooltip>
        </span>
      ),
      render: () => (
        <div
          style={{
            minWidth: '50px',
          }}
        ></div>
      ),
    },
    {
      title: '测评结果',
      key: 'result',
      render: (_, record) => (
        <>
          <Button
            type="link"
            loading={showEvaluationLoading}
            onClick={async () => {
              runShowEvaluation({
                evaluate_code: record?.evaluate_code,
              });
            }}
          >
            评分明细
          </Button>
          <Button
            type="link"
            loading={commonLoading}
            onClick={async () => {
              setCommonLoading(true);
              let response = await downloadEvaluation({
                evaluate_code: record?.evaluate_code,
              });
              const contentType = response.headers['content-type'];

              if (contentType.includes('application/json')) {
                // 如果是 JSON，解析错误信息
                const reader = new FileReader();
                reader.onload = () => {
                  try {
                    const error = JSON.parse(reader.result as string);
                    message.error(error.err_msg);
                    // 在页面或通知系统中展示错误信息
                  } catch (parseError) {
                    console.error('Failed to parse error response:', parseError);
                  }
                };
                reader.readAsText(response.data as any);
              } else {
                // 从响应头中获取文件名
                const contentDisposition = response.headers['content-disposition'];
                let filename = 'downloaded_file.xlsx';
                if (contentDisposition) {
                  const match = contentDisposition.match(/filename\*?="?(.+)"/);
                  if (match[1]) {
                    filename = decodeURIComponent(match[1]);
                  }
                }

                // 创建 URL 并触发下载
                const url = window.URL.createObjectURL(
                  new Blob([response.data as any], {
                    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                  }),
                );
                console.log(url, response);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url); // 释放内存
              }
              setCommonLoading(false);
            }}
          >
            下载
          </Button>
        </>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: '25%',
      render: (_, record) => (
        <>
          <Popconfirm
            title="确认删除吗"
            onConfirm={async () => {
              let [, , res] = await apiInterceptors(
                delEvaluation({
                  evaluation_code: record?.evaluate_code,
                }),
              );
              if (res?.success == true) {
                message.success('删除成功');
                getEvaluationsRefresh();
              }
            }}
          >
            <Button type="link">删除</Button>
          </Popconfirm>
        </>
      ),
    },
  ];
  const handleModalClose = () => {
    setIsModalVisible(false);
  };
  return (
    <ConfigProvider
      theme={{
        components: {
          Segmented: {
            itemSelectedBg: '#2867f5',
            itemSelectedColor: 'white',
          },
        },
      }}
    >
      <div className="flex flex-col h-full w-full  dark:bg-gradient-dark bg-gradient-light bg-cover bg-center">
        <div className="px-6 py-2 overflow-y-auto">
          <Segmented
            className="backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 border-2 border-white rounded-lg shadow p-1 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60"
            options={[
              {
                label: '评测数据',
                value: 'evaluations',
              },
              {
                label: '数据集',
                value: 'dataSet',
              },
            ]}
            onChange={(type) => {
              setCurrentTable(type as string);
            }}
            value={currentTable}
          />
          {currentTable === 'dataSet' && (
            <>
              <div className="flex flex-row-reverse mb-4">
                <Button
                  className="border-none text-white bg-button-gradient h-full"
                  onClick={() => {
                    setIsDataSetModalOpen(true);
                    setIsAddDataSet(true);
                  }}
                >
                  添加数据集
                </Button>
              </div>
              <Table
                pagination={{
                  total: dataSetsTotal,
                  onChange(page) {
                    runGetDataSets(page);
                  },
                }}
                scroll={{ x: 1300 }}
                loading={getDataSetsLoading}
                columns={columns}
                dataSource={dataSetsList}
              />
            </>
          )}
          {currentTable === 'evaluations' && (
            <>
              <div className="flex flex-row-reverse mb-4">
                <Button
                  className="border-none text-white bg-button-gradient h-full"
                  onClick={() => {
                    setIsModalOpen(true);
                  }}
                >
                  发起评测
                </Button>
              </div>
              <Table
                pagination={{
                  total: evaluationTotal,
                  onChange(page) {
                    runGetEvaluations(page);
                  },
                }}
                rowKey={(record) => record.evaluate_code}
                expandable={{
                  expandedRowRender: ({ average_score, log_info }) => {
                    return (
                      <div className="flex flex-col gap-2">
                        {(() => {
                          if (!average_score) return <></>;
                          try {
                            const jsonData = JSON.parse(average_score);
                            return (
                              <div className="flex flex-row gap-1">
                                {Object.entries(jsonData)?.map((item) => {
                                  let [k, v] = item;
                                  return <Statistic title={k} key={k} value={v} />;
                                })}
                              </div>
                            );
                          } catch {
                            return <></>;
                          }
                        })()}
                        {log_info && (
                          <div>
                            <span className="text-gray-500 text-sm">log：</span>
                            <span>{log_info}</span>
                          </div>
                        )}
                      </div>
                    );
                  },
                }}
                scroll={{ x: '100%' }}
                loading={getEvaluationsLoading}
                columns={evaluationsColumns}
                dataSource={evaluationList}
              />
            </>
          )}
          <Modal
            title="发起测评"
            open={isModalOpen}
            onOk={async () => {
              const values = await form.validateFields();
              setEvaluationModalLoading(true);
              if (values) {
                let [, , res] = await apiInterceptors(
                  createEvaluations({
                    ...values,
                  }),
                );
                if (res?.success) {
                  message.success('发起成功');
                  getEvaluationsRefresh();
                  form.resetFields();
                }
              }
              setIsModalOpen(false);
              setEvaluationModalLoading(false);
            }}
            confirmLoading={evaluationModalLoading}
            onCancel={() => {
              setIsModalOpen(false);
            }}
          >
            <Form name="basic" form={form} initialValues={{ remember: true }} autoComplete="off" labelCol={{ span: 4 }} wrapperCol={{ span: 20 }}>
              <Form.Item name="scene_key" label="场景类型" rules={[{ required: true }]}>
                <Select
                  options={[
                    {
                      value: 'recall',
                      label: 'recall',
                    },
                    {
                      value: 'app',
                      label: 'app',
                    },
                  ]}
                  onChange={async (value) => {
                    //getSceneValueOptions
                    setSceneValueOptionLoading(true);
                    form.setFieldValue('scene_value', '');
                    if (value === 'recall') {
                      let res = await getSpaceList();
                      if (res.data.success) {
                        setSceneValueOptions(res.data.data.map((i) => ({ label: i.name, value: i.id.toString() })));
                      }
                    } else {
                      let res = await getAppList({});
                      if (res.data.success) {
                        setSceneValueOptions(res.data.data.app_list.map((i) => ({ label: i.app_name, value: i.app_code })));
                      }
                    }
                    setSceneValueOptionLoading(false);
                  }}
                ></Select>
              </Form.Item>
              <Form.Item name="scene_value" label="场景参数" rules={[{ required: true }]}>
                <Select
                  loading={sceneValueOptionLoading}
                  disabled={sceneValueOptionLoading}
                  options={sceneValueOptions}
                  onChange={(value) => {
                    if (form.getFieldValue('scene_key')) {
                      runGetMetrics({ scene_key: form.getFieldValue('scene_key'), scene_value: value });
                    }
                  }}
                ></Select>
              </Form.Item>
              <Form.Item name="parallel_num" label="并行参数" rules={[{ required: true }]} initialValue={1}>
                <Input></Input>
              </Form.Item>
              <Form.Item name="datasets" label="数据集" rules={[{ required: true }]}>
                <Select options={dataSetsOptions}></Select>
              </Form.Item>
              <Form.Item name="evaluate_metrics" label="评测指标" rules={[{ required: useWatch('scene_key', form) === 'app' }]}>
                <Select loading={getMetricsLoading} disabled={getMetricsLoading} options={metricOptions}></Select>
              </Form.Item>
            </Form>
          </Modal>
          <Modal
            title={isAddDataSet ? '添加数据集' : '编辑数据集'}
            open={isDataSetModalOpen}
            confirmLoading={dataSetModalLoading}
            onOk={() => {
              dataSetForm.validateFields().then((values) => {
                setDataSetModalLoading(true);
                if (isAddDataSet) {
                  const storageType = values.storage_type;
                  if (storageType === 'oss') {
                    // 创建FormData对象
                    const formData = new FormData();
                    formData.append('dataset_name', values.dataset_name);
                    values.members && formData.append('members', values.members.join(','));

                    const file = values.doc_file.file; // 获取文件对象
                    formData.append('doc_file', file, file.name);

                    uploadDataSetsFile(formData)
                      .then((response) => {
                        console.log(response);
                        if (response.data.success) {
                          message.success('上传成功');
                          runGetDataSets();
                        } else {
                          message.error(response.data.err_msg);
                        }
                      })
                      .catch((error) => {
                        console.error('上传失败', error);
                        message.error(error?.response?.data?.err_msg || '上传失败');
                      })
                      .finally(() => {
                        setIsDataSetModalOpen(false);
                        setDataSetModalLoading(false);
                      });
                  } else if (storageType === 'db') {
                    uploadDataSetsContent({
                      dataset_name: values.dataset_name,
                      members: values.members.join(','),
                      content: values.content,
                    })
                      .then((res) => {
                        console.log(res);
                        if (res.data.success) {
                          message.success('上传成功');
                          runGetDataSets();
                        } else {
                          message.error(res.data.err_msg);
                        }
                      })
                      .catch((err) => {
                        console.log(err);
                        message.error(err?.response?.data?.err_msg || '上传失败');
                      })
                      .finally(() => {
                        setIsDataSetModalOpen(false);
                        setDataSetModalLoading(false);
                        dataSetForm.resetFields();
                      });
                  }
                } else {
                  updateEvaluations({
                    code: currentEvaluationCode,
                    members: values.members.join(','),
                  })
                    .then((res) => {
                      if (res.data.success) {
                        message.success('更新成功');
                        runGetDataSets();
                      } else {
                        message.error(res.data.err_msg);
                      }
                    })
                    .catch((err) => {
                      console.log(err);
                      message.error('更新失败');
                    })
                    .finally(() => {
                      setIsDataSetModalOpen(false);
                      setDataSetModalLoading(false);
                    });
                }
              });
            }}
            onCancel={() => {
              setIsDataSetModalOpen(false);
            }}
          >
            <Form
              name="basic"
              form={dataSetForm}
              initialValues={{ remember: true }}
              autoComplete="off"
              labelCol={{ span: 4 }}
              wrapperCol={{ span: 20 }}
            >
              <Form.Item name="dataset_name" label="名称" rules={[{ required: true }]}>
                <Input disabled={!isAddDataSet} />
              </Form.Item>
              <Form.Item name="members" label="成员">
                <Select mode="tags" />
              </Form.Item>
              {isAddDataSet && (
                <Form.Item name="storage_type" label="储存类型" rules={[{ required: true }]}>
                  <Select options={storageTypeOptions} />
                </Form.Item>
              )}
              {useWatch('storage_type', dataSetForm) === 'oss' && isAddDataSet && (
                <Form.Item name="doc_file" label="doc_file" rules={[{ required: true }]}>
                  <Upload
                    name="dataSet"
                    maxCount={1}
                    beforeUpload={(file) => {
                      // console.log(file, dataSetForm.getFieldsValue());
                      dataSetForm.setFieldsValue({
                        doc_file: file,
                      });
                      return false;
                    }}
                    onRemove={() => {
                      dataSetForm.setFieldsValue({
                        doc_file: undefined,
                      });
                    }}
                  >
                    <Button icon={<UploadOutlined />}>Click to Upload</Button>
                  </Upload>
                </Form.Item>
              )}
              {useWatch('storage_type', dataSetForm) === 'db' && isAddDataSet && (
                <Form.Item name="content" label="content" rules={[{ required: true }]}>
                  <TextArea rows={8} />
                </Form.Item>
              )}
            </Form>
          </Modal>
          <Modal
            title="评分明细"
            open={isModalVisible}
            onOk={handleModalClose}
            onCancel={handleModalClose}
            styles={{
              body: {
                maxHeight: '500px',
                overflowY: 'auto',
                minWidth: '700px',
              },
            }}
            style={{
              minWidth: '750px',
            }}
            footer={[
              <Button key="back" onClick={handleModalClose}>
                返回
              </Button>,
            ]}
          >
            <Table
              columns={Object.keys(evaluationShowData?.[0]).map((key) => ({
                title: key,
                dataIndex: key,
                key,
              }))}
              style={{
                minWidth: '700px',
              }}
              dataSource={evaluationShowData}
              rowKey={(record, index) => index?.toString()!} // 使用索引作为 key
              pagination={false} // 禁用分页
            />
          </Modal>
        </div>
      </div>
    </ConfigProvider>
  );
};

export default Evaluation;
