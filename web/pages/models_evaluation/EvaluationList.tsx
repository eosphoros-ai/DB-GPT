import { Button, Table, Tag, Tooltip } from "antd";
import React, { useEffect } from "react";
import { EvaluationItem } from "@/types/models_evaluation";
import { useEvaluation } from "./context/EvaluationContext";
import { useRouter } from "next/router";

interface EvaluationListProps {
  filterValue?: string;
  type?: string;
}

export const EvaluationList: React.FC<EvaluationListProps> = (props) => {
  const { filterValue = '', type = 'all' } = props;
  const { data, loading, getModelsEvaluation } = useEvaluation();

  const router = useRouter();

  useEffect(() => {
    getModelsEvaluation?.(1, 20);
  }, []);

  const columns = [
    {
      title: 'ID',
      dataIndex: 'evaluate_code',
      key: 'evaluate_code',
      width: '20%',
    },
    {
      title: '任务名称',
      dataIndex: 'scene_value',
      key: 'scene_value',
      width: '10%',
    },
    {
      title: '创建时间',
      dataIndex: 'gmt_create',
      key: 'gmt_create',
      width: '10%',
    },
    {
      title: '完成时间',
      dataIndex: 'gmt_modified',
      key: 'gmt_modified',
      width: '10%',
    },
    {
      title: '模型名称',
      dataIndex: 'model_list',
      key: 'model_list',
      width: '10%',
      render: (model_list: string[]) => (
        <span>{model_list.join(',')}</span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'state',
      key: 'state',
      render: (state: string, record: EvaluationItem) => {
        let color = 'default';
        let text = state;
        
        if (state === 'running') {
          color = 'blue';
          text = '运行中';
        } else if (state === 'complete') {
          color = 'green';
          text = '已完成';
        } else if (state === 'failed') {
          color = 'red';
          text = '失败';
        } else if (state === 'pending') {
          color = 'orange';
          text = '待处理';
        }

        if (record?.state === 'failed') {
          return (
            <Tooltip title={record.log_info}>
              <Tag color={color}>{text}</Tag>
            </Tooltip>
          )
        }

        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '可执行率',
      key: 'executable_rate',
      width: '10%',
      render: () => <span>--</span>, // 暂时显示默认值
    },
    {
      title: '正确率',
      key: 'correct_rate',
      width: '10%',
      render: () => <span>--</span>, // 暂时显示默认值
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: EvaluationItem) => {
        return (
          <Button type="link" onClick={() => router.push(`/models_evaluation/${record.evaluate_code}`)} disabled={record.state !== 'complete'}>查看</Button>
        );
      },
    },
  ];

  return (
    <Table
      className='w-full'
      pagination={{
        total: data?.total_count || 0,
        current: data?.page || 1,
        pageSize: data?.page_size || 20,
        onChange: (page, pageSize) => getModelsEvaluation?.(page, pageSize),
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50', '100'],
      }}
      loading={loading}
      columns={columns}
      dataSource={data?.items || []}
      rowKey="evaluate_code"
    />
  );
};