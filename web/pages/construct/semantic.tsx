import { apiInterceptors } from '@/client/api';
import {
  SemanticCoverage,
  SemanticEntry,
  SemanticExample,
  SemanticMetric,
  SemanticRelation,
  SemanticRule,
  SemanticSpace,
  SemanticTable,
  getSemanticCoverage,
  getSemanticEntries,
  getSemanticExamples,
  getSemanticMetrics,
  getSemanticRelations,
  getSemanticRules,
  getSemanticSpace,
  getSemanticSpaces,
  getSemanticTables,
  postEntryReview,
  postMetricPublish,
  postRuleStatus,
  postSemanticActivate,
  postSemanticBackfill,
  postSemanticSync,
} from '@/client/api/semantic';
import ConstructLayout from '@/new-components/layout/Construct';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useAsyncEffect } from 'ahooks';
import { Button, Modal, Select, Space, Statistic, Table, Tabs, Tag, Typography, message } from 'antd';
import { useRouter } from 'next/router';
import { useState } from 'react';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  activated: 'green',
  not_activated: 'orange',
  published: 'green',
  draft: 'orange',
  stale: 'red',
  rejected: 'default',
  active: 'green',
  inactive: 'default',
  deleted: 'red',
};

const SemanticCenter = () => {
  const router = useRouter();
  const dsId = router.query.ds ? Number(router.query.ds) : null;

  const [spaces, setSpaces] = useState<SemanticSpace[]>([]);
  const [space, setSpace] = useState<SemanticSpace | null>(null);
  const [coverage, setCoverage] = useState<SemanticCoverage | null>(null);
  const [tables, setTables] = useState<SemanticTable[]>([]);
  const [entries, setEntries] = useState<SemanticEntry[]>([]);
  const [metrics, setMetrics] = useState<SemanticMetric[]>([]);
  const [examples, setExamples] = useState<SemanticExample[]>([]);
  const [relations, setRelations] = useState<SemanticRelation[]>([]);
  const [rules, setRules] = useState<SemanticRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [activateId, setActivateId] = useState<number | null>(null);
  const [sampling, setSampling] = useState('42');
  const [runDrafts, setRunDrafts] = useState('no');
  const [embedding, setEmbedding] = useState('bge-large-zh');

  const loadSpaces = async () => {
    setLoading(true);
    const [, data] = await apiInterceptors(getSemanticSpaces());
    setSpaces(data ?? []);
    setLoading(false);
  };

  const loadDetail = async (id: number) => {
    setLoading(true);
    const [, sp] = await apiInterceptors(getSemanticSpace(id));
    const [, cov] = await apiInterceptors(getSemanticCoverage(id));
    const [, tb] = await apiInterceptors(getSemanticTables(id));
    const [, en] = await apiInterceptors(getSemanticEntries(id));
    const [, me] = await apiInterceptors(getSemanticMetrics(id));
    const [, ex] = await apiInterceptors(getSemanticExamples(id));
    const [, re] = await apiInterceptors(getSemanticRelations(id));
    const [, ru] = await apiInterceptors(getSemanticRules(id));
    setSpace(sp);
    setCoverage(cov);
    setTables(tb ?? []);
    setEntries(en ?? []);
    setMetrics(me ?? []);
    setExamples(ex ?? []);
    setRelations(re ?? []);
    setRules(ru ?? []);
    setLoading(false);
  };

  useAsyncEffect(async () => {
    if (dsId) await loadDetail(dsId);
    else await loadSpaces();
  }, [dsId]);

  const doBackfill = async () => {
    const [, res] = await apiInterceptors(postSemanticBackfill());
    message.success(`回填完成：同步 ${res?.synced?.length ?? 0} 个连接，失败 ${res?.failed?.length ?? 0}`);
    await loadSpaces();
  };

  const doSync = async (id: number) => {
    const [, report] = await apiInterceptors(postSemanticSync(id));
    message.success(`同步完成：新增表 ${report?.tables_added ?? 0}，删除 ${report?.tables_deleted ?? 0}`);
    if (dsId) await loadDetail(id);
    else await loadSpaces();
  };

  const doActivate = async () => {
    if (activateId == null) return;
    const [, res] = await apiInterceptors(
      postSemanticActivate(activateId, {
        sampling_limit: sampling === 'all' ? 9999 : Number(sampling),
        run_draft_generation: runDrafts === 'yes',
        embedding_model: embedding,
      }),
    );
    message.success(`已激活，白名单 ${res?.whitelist ?? 0} 表`);
    setActivateId(null);
    if (dsId) await loadDetail(activateId);
    else await loadSpaces();
  };

  const review = async (entryId: number, action: 'confirm' | 'reject') => {
    const [, res] = await apiInterceptors(postEntryReview(entryId, { action }));
    message.success(`条目 ${entryId} → ${res?.status}`);
    if (dsId) await loadDetail(dsId);
  };

  const publish = async (metricId: number) => {
    const [, res] = await apiInterceptors(postMetricPublish(metricId, { change_note: 'publish via UI' }));
    message.success(`指标已发布 v${res?.version}`);
    if (dsId) await loadDetail(dsId);
  };

  const toggleRule = async (ruleId: number, status: string) => {
    await apiInterceptors(postRuleStatus(ruleId, status));
    if (dsId) await loadDetail(dsId);
  };

  if (!dsId) {
    return (
      <ConstructLayout>
        <div className='p-6'>
          <Space>
            <Title level={4} style={{ margin: 0 }}>语义中心</Title>
            <Button size='small' onClick={doBackfill}>登记存量连接</Button>
          </Space>
          <Text type='secondary'>
            每个数据源连接自动创建一个语义空间（L1 元数据自动同步、只读）；“激活治理”后点亮标注/指标/样例/规则与检索消费。
          </Text>
          <Table
            rowKey='id'
            loading={loading}
            className='mt-4'
            dataSource={spaces}
            columns={[
              { title: '空间', dataIndex: 'space_name' },
              { title: '来源连接', dataIndex: 'conn_id' },
              {
                title: '状态',
                dataIndex: 'status',
                render: (s: string) => <Tag color={STATUS_COLOR[s] ?? 'default'}>{s}</Tag>,
              },
              { title: '表数', dataIndex: 'table_count' },
              { title: 'chunks', dataIndex: 'chunk_count' },
              { title: 'embedding', dataIndex: 'embedding_model' },
              {
                title: '操作',
                render: (_, row: SemanticSpace) => (
                  <Space>
                    <Button size='small' type='primary' onClick={() => router.push(`/construct/semantic?ds=${row.id}`)}>
                      进入
                    </Button>
                    <Button size='small' onClick={() => doSync(row.id)}>
                      同步
                    </Button>
                    {row.status === 'not_activated' && (
                      <Button size='small' type='default' onClick={() => setActivateId(row.id)}>
                        激活治理
                      </Button>
                    )}
                  </Space>
                ),
              },
            ]}
          />
          <Modal
            title='激活治理'
            open={activateId != null}
            onOk={doActivate}
            onCancel={() => setActivateId(null)}
            okText='确认激活'
          >
            <Space direction='vertical' className='w-full'>
              <div>
                采样范围：
                <Select
                  value={sampling}
                  onChange={setSampling}
                  options={[
                    { value: '42', label: '高频 top 42 表（推荐）' },
                    { value: 'all', label: '全表（分批）' },
                  ]}
                />
              </div>
              <div>
                立即跑 LLM 草稿生成：
                <Select
                  value={runDrafts}
                  onChange={setRunDrafts}
                  options={[
                    { value: 'no', label: '暂不跑' },
                    { value: 'yes', label: '跑（消耗 token）' },
                  ]}
                />
              </div>
              <div>
                embedding 模型（换则全量重建）：
                <Select
                  value={embedding}
                  onChange={setEmbedding}
                  options={[
                    { value: 'bge-large-zh', label: 'bge-large-zh' },
                    { value: 'text-embedding-v3', label: 'text-embedding-v3' },
                  ]}
                />
              </div>
            </Space>
          </Modal>
        </div>
      </ConstructLayout>
    );
  }

  const tabItems = [
    {
      key: 'catalog',
      label: '① 元数据目录',
      children: (
        <Table
          rowKey='id'
          size='small'
          dataSource={tables}
          columns={[
            { title: '表', dataIndex: 'table_name' },
            { title: 'comment', dataIndex: 'table_comment' },
            { title: '类型', dataIndex: 'table_type' },
            {
              title: '白名单',
              dataIndex: 'is_whitelisted',
              render: (v: boolean) => (v ? <Tag color='green'>是</Tag> : <Tag>否</Tag>),
            },
            { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
          ]}
        />
      ),
    },
    {
      key: 'entries',
      label: `② 语义标注${coverage?.entries?.draft ? ` (${coverage.entries.draft} 待审)` : ''}`,
      children: (
        <Table
          rowKey='id'
          size='small'
          dataSource={entries}
          columns={[
            { title: '类型', dataIndex: 'entry_type' },
            { title: '名称', dataIndex: 'entry_name' },
            { title: '描述', dataIndex: 'entry_comment', ellipsis: true },
            { title: '来源', dataIndex: 'provenance' },
            { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
            {
              title: '操作',
              render: (_, row: SemanticEntry) =>
                row.status === 'draft' || row.status === 'stale' ? (
                  <Space>
                    <Button size='small' type='primary' onClick={() => review(row.id, 'confirm')}>
                      确认发布
                    </Button>
                    <Button size='small' danger onClick={() => review(row.id, 'reject')}>
                      驳回
                    </Button>
                  </Space>
                ) : null,
            },
          ]}
        />
      ),
    },
    {
      key: 'metrics',
      label: '③ 指标口径',
      children: (
        <Table
          rowKey='id'
          size='small'
          dataSource={metrics}
          columns={[
            { title: '指标', dataIndex: 'metric_name' },
            { title: '公式', dataIndex: 'formula', ellipsis: true },
            { title: '类型', dataIndex: 'metric_type' },
            { title: '版本', dataIndex: 'version' },
            { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
            {
              title: '操作',
              render: (_, row: SemanticMetric) =>
                row.status === 'draft' ? (
                  <Button size='small' type='primary' onClick={() => publish(row.id)}>
                    发布
                  </Button>
                ) : null,
            },
          ]}
        />
      ),
    },
    {
      key: 'examples',
      label: '④ 样例库',
      children: (
        <Table
          rowKey='id'
          size='small'
          dataSource={examples}
          columns={[
            { title: '问题', dataIndex: 'question', ellipsis: true },
            { title: 'SQL', dataIndex: 'sql_text', ellipsis: true },
            { title: '来源', dataIndex: 'source' },
            { title: '使用次数', dataIndex: 'use_count' },
            { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
          ]}
        />
      ),
    },
    {
      key: 'relations',
      label: '⑤ 关系/血缘',
      children: (
        <Table
          rowKey='id'
          size='small'
          dataSource={relations}
          columns={[
            { title: '左表id', dataIndex: 'left_table_id' },
            { title: '左列id', dataIndex: 'left_column_id' },
            { title: '右表id', dataIndex: 'right_table_id' },
            { title: '右列id', dataIndex: 'right_column_id' },
            { title: '类型', dataIndex: 'relation_type' },
            { title: 'join 条件', dataIndex: 'join_condition', ellipsis: true },
            { title: '置信度', dataIndex: 'confidence' },
          ]}
        />
      ),
    },
    {
      key: 'rules',
      label: '⑥ 规则护栏',
      children: (
        <Table
          rowKey='id'
          size='small'
          dataSource={rules}
          columns={[
            { title: '规则', dataIndex: 'rule_name' },
            { title: '类型', dataIndex: 'rule_type' },
            { title: '优先级', dataIndex: 'priority' },
            { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
            {
              title: '操作',
              render: (_, row: SemanticRule) => (
                <Button size='small' onClick={() => toggleRule(row.id, row.status === 'active' ? 'inactive' : 'active')}>
                  {row.status === 'active' ? '停用' : '启用'}
                </Button>
              ),
            },
          ]}
        />
      ),
    },
  ];

  return (
    <ConstructLayout>
      <div className='p-6'>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => router.push('/construct/semantic')}>
            空间列表
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            {space?.space_name ?? `space#${dsId}`}
          </Title>
          <Tag color={STATUS_COLOR[space?.status ?? '']}>{space?.status}</Tag>
          <Button size='small' onClick={() => doSync(dsId)}>
            同步
          </Button>
        </Space>
        {coverage && (
          <Space size='large' className='mt-4 mb-2'>
            <Statistic title='表' value={coverage.tables} />
            <Statistic title='白名单' value={coverage.whitelisted} />
            <Statistic title='已标注表' value={coverage.tables_annotated} />
            <Statistic title='覆盖率' value={coverage.coverage_pct} suffix='%' />
            <Statistic title='待审标注' value={coverage.entries?.draft ?? 0} />
            <Statistic title='已发布指标' value={coverage.metrics?.published ?? 0} />
          </Space>
        )}
        <Tabs items={tabItems} />
      </div>
    </ConstructLayout>
  );
};

export default SemanticCenter;
