import {
  adaptDashboardTemplate,
  generateDashboardTemplate,
  getDashboardTemplateFeatures,
  inspectTemplateSource,
  previewDashboardTemplate,
  type DashboardTemplateFeatures,
  type TemplatePreview,
  type TemplateSourceField,
  type TemplateSourceInfo,
  type TemplateSourceJoin,
  type TemplateSourceMapping,
} from '@/client/api/dashboard';
import { SELECTED_MODEL_STORAGE_KEY } from '@/lib/model-runtime';
import {
  CheckCircleOutlined,
  CommentOutlined,
  DeleteOutlined,
  PlusOutlined,
  SlidersOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Alert, Button, Checkbox, Collapse, Input, Modal, Radio, Select, Spin, Steps, Tag } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
import type { CatalogTemplate } from './dashboard-catalog';
import { describeDashboardError } from './dashboard-errors';
import { dashboardSourceLabel } from './dashboard-source-label';
import DashboardRenderer from './DashboardRenderer';
import styles from './DashboardTemplateSetup.module.css';

const grainLabels = {
  store_week: '一间门店的一周记录',
  order: '一笔订单',
  order_line: '一笔商品订单明细',
  payment: '一笔支付记录',
  incident: '一条去重后的工单',
  measurement: '一次独立采样 / 测量',
  student: '一名学生的一门课程记录',
  product: '一项商品的当前库存快照',
};
const emptyMapping = (): TemplateSourceMapping => ({
  table: '',
  fields: {},
  joins: [],
  date_format: 'iso',
  unit: '',
  interval: 'month',
  grain: 'order',
});
const fieldValue = (field?: TemplateSourceField) => (field ? JSON.stringify(field) : undefined);

export default function DashboardTemplateSetup({
  template,
  sources,
  onClose,
}: {
  template: CatalogTemplate;
  sources: string[];
  onClose: () => void;
}) {
  const router = useRouter();
  const [source, setSource] = useState(template.sourceNames.find(name => sources.includes(name)) || sources[0] || '');
  const [info, setInfo] = useState<TemplateSourceInfo | null>(null);
  const [manual, setManual] = useState(false);
  const [aiAssisted, setAiAssisted] = useState(true);
  const [features, setFeatures] = useState<DashboardTemplateFeatures | null>(null);
  const [aiPrompt, setAiPrompt] = useState('');
  useEffect(() => {
    let active = true;
    void getDashboardTemplateFeatures(template.id)
      .then(response => {
        if (active && response.data.success) {
          setFeatures(response.data.data);
          setAiPrompt(response.data.data.prompt);
        }
      })
      .catch(() => {
        if (active)
          setAiPrompt(
            `参考「${template.title}」的布局与样式，使用所选数据源创建看板。${template.description} 字段不匹配时根据真实数据自适应调整。`,
          );
      });
    return () => {
      active = false;
    };
  }, [template.id, template.title, template.description]);
  const [mapping, setMapping] = useState<TemplateSourceMapping>(emptyMapping);
  const [confirmedGrain, setConfirmedGrain] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<TemplatePreview | null>(null);
  const epoch = useRef(0);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      setLoading(true);
      setInfo(null);
      setPreview(null);
      setError('');
      setMapping(emptyMapping());
      setConfirmedGrain(false);
      if (!source) {
        setLoading(false);
        return;
      }
      try {
        const r = await inspectTemplateSource(template.id, source);
        if (!r.data.success) throw new Error(r.data.err_msg || '无法读取数据表');
        if (active) {
          setInfo(r.data.data);
          setManual(!r.data.data.builtin_available);
          setMapping({
            ...emptyMapping(),
            grain: r.data.data.grain,
            table: r.data.data.tables.length === 1 ? r.data.data.tables[0].name : '',
          });
        }
      } catch (e) {
        if (active) setError(describeDashboardError(e, '数据源不可用'));
      } finally {
        if (active) setLoading(false);
      }
    }, 0);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [source, template.id]);
  const editMapping = (patch: Partial<TemplateSourceMapping>) => {
    epoch.current++;
    setPreview(null);
    setError('');
    setMapping(value => ({ ...value, ...patch }));
  };
  const availableTables = [mapping.table, ...mapping.joins.map(j => j.table)].filter(Boolean);
  const fieldOptions = (tables = availableTables) =>
    (info?.tables || [])
      .filter(t => tables.includes(t.name))
      .map(t => ({
        label: t.name,
        options: t.columns.map(c => ({
          label: `${t.name}.${c.name} · ${c.type}`,
          value: fieldValue({ table: t.name, column: c.name })!,
        })),
      }));
  const requiredRoles = info?.roles.filter(r => r.required) || [];
  const missingRoles = requiredRoles.filter(r => !mapping.fields[r.id]);
  const fieldsComplete = !!info && missingRoles.length === 0;
  const joinsComplete = mapping.joins.every(j => j.table && j.left.table && j.left.column && j.right_column);
  const mappingNextStep = !mapping.table
    ? '请先选择业务明细表，下面的字段选择才会开放。'
    : missingRoles.length
      ? `还需匹配：${missingRoles.map(r => r.label).join('、')}。`
      : !joinsComplete
        ? '请补全关联表的连接字段，或移除不需要的关联。'
        : !mapping.unit.trim()
          ? '请填写主要数值的单位。'
          : !confirmedGrain
            ? '请确认明细表每行代表的业务含义和数值单位。'
            : '匹配已填写完整，可以验证查询并预览。';
  const canPreview =
    !!source &&
    !!info &&
    (aiAssisted ||
      !manual ||
      (mapping.table && mapping.unit.trim() && confirmedGrain && fieldsComplete && joinsComplete));
  const check = async () => {
    const version = ++epoch.current;
    setBusy(true);
    setError('');
    try {
      const response = aiAssisted
        ? await adaptDashboardTemplate(
            template.id,
            source,
            aiPrompt,
            localStorage.getItem(SELECTED_MODEL_STORAGE_KEY) || undefined,
          )
        : await previewDashboardTemplate(template.id, source, manual ? mapping : undefined);
      if (!response.data.success) throw new Error(response.data.err_msg || '预览验证失败');
      if (epoch.current === version) setPreview(response.data.data);
    } catch (e) {
      if (epoch.current === version) setError(describeDashboardError(e, '预览验证失败'));
    } finally {
      setBusy(false);
    }
  };
  const updateJoin = (index: number, patch: Partial<TemplateSourceJoin>) =>
    editMapping({ joins: mapping.joins.map((j, i) => (i === index ? { ...j, ...patch } : j)) });
  return (
    <Modal
      open
      title={template.title}
      width={1180}
      onCancel={() => {
        if (!busy) onClose();
      }}
      maskClosable={!busy}
      closable={!busy}
      footer={
        <div className={styles.footer}>
          {!preview && !aiAssisted && manual && info && (
            <span className={styles.mappingStatus} role='status'>
              {mappingNextStep}
            </span>
          )}
          <Button disabled={busy} onClick={onClose}>
            取消
          </Button>
          {preview ? (
            <>
              <Button disabled={busy} onClick={() => setPreview(null)}>
                重新匹配
              </Button>
              <Button
                type='primary'
                loading={busy}
                onClick={async () => {
                  if (busy) return;
                  setBusy(true);
                  setError('');
                  try {
                    const r = await generateDashboardTemplate(
                      template.id,
                      source,
                      aiAssisted ? undefined : manual ? mapping : undefined,
                      aiAssisted ? preview.schema : undefined,
                    );
                    if (!r.data.success) throw new Error(r.data.err_msg || '生成失败');
                    await router.push(`/dashboards/${r.data.data.id}`);
                  } catch (e) {
                    setError(describeDashboardError(e, '生成失败，请检查数据源'));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                创建看板
              </Button>
            </>
          ) : (
            <Button
              type='primary'
              disabled={!canPreview || busy || loading}
              loading={busy}
              onClick={() => void check()}
            >
              {aiAssisted ? 'AI 适配并预览' : '验证并预览'}
            </Button>
          )}
        </div>
      }
    >
      <Steps
        className={styles.steps}
        size='small'
        current={preview ? 2 : manual ? 1 : 0}
        items={[{ title: '选择数据' }, { title: 'AI 适配 / 字段匹配' }, { title: '预览并创建' }]}
      />
      {error && <Alert className={styles.error} type='error' showIcon message={error} />}
      {preview ? (
        <>
          <Alert
            type='success'
            showIcon
            message={
              preview.adaptation
                ? `AI 适配完成，${preview.validation.widgets} 个组件查询验证通过`
                : `已读取 ${preview.validation.records?.toLocaleString('zh-CN')} 条明细，${preview.validation.widgets} 个组件及年份、分类筛选验证通过`
            }
            description='预览尚未保存。确认后创建看板，后续可继续编辑布局、筛选器或让数据助理修改。'
          />
          {!!preview.adaptation?.changes?.length && (
            <details className='my-4 rounded-lg border border-[var(--app-border)] p-3'>
              <summary className='cursor-pointer text-sm font-medium'>AI 做了哪些适配</summary>
              <ul className='mt-2 list-disc space-y-1 pl-5 text-xs text-[var(--app-muted)]'>
                {preview.adaptation.changes.map((change, index) => (
                  <li key={index}>{change}</li>
                ))}
              </ul>
            </details>
          )}
          <div className={styles.preview}>
            <DashboardRenderer schema={preview.schema} snapshot={preview.snapshot} />
          </div>
        </>
      ) : (
        <div className={styles.form}>
          <label className={styles.full}>
            使用哪个数据源生成看板
            <Select
              aria-label='模板数据源'
              showSearch
              optionFilterProp='label'
              value={source || undefined}
              disabled={busy}
              options={sources.map(value => ({ value, label: dashboardSourceLabel(value) }))}
              onChange={value => {
                epoch.current++;
                setSource(value);
              }}
            />
            <span className='mt-2 block text-xs text-[var(--app-muted)]'>
              模板提供布局与计算方式，图表将查询这里所选数据源的实际数据。
            </span>
          </label>
          {loading ? (
            <Spin />
          ) : (
            info && (
              <>
                <p className={styles.full}>{template.description}</p>
                <Radio.Group
                  className={`${styles.full} ${styles.matchingModes}`}
                  aria-label='模板匹配方式'
                  value={aiAssisted ? 'ai' : manual ? 'manual' : 'preset'}
                  disabled={busy}
                  onChange={event => {
                    epoch.current++;
                    setAiAssisted(event.target.value === 'ai');
                    setManual(event.target.value === 'manual');
                    setPreview(null);
                    setError('');
                  }}
                >
                  <Radio value='ai' className={styles.matchOption}>
                    <span className={styles.matchIcon}>
                      <ThunderboltOutlined />
                    </span>
                    <span className={styles.matchCopy}>
                      <strong>AI 智能适配</strong>
                      <small>理解数据，自动调整指标与图表</small>
                    </span>
                  </Radio>
                  {info.builtin_available && (
                    <Radio value='preset' className={styles.matchOption}>
                      <span className={styles.matchIcon}>
                        <CheckCircleOutlined />
                      </span>
                      <span className={styles.matchCopy}>
                        <strong>使用预设匹配</strong>
                        <small>沿用模板已配置的数据关系</small>
                      </span>
                    </Radio>
                  )}
                  {['sqlite', 'sqlite3'].includes(info.dialect) && (
                    <Radio value='manual' className={styles.matchOption}>
                      <span className={styles.matchIcon}>
                        <SlidersOutlined />
                      </span>
                      <span className={styles.matchCopy}>
                        <strong>手动匹配字段</strong>
                        <small>自主选择字段与计算口径</small>
                      </span>
                    </Radio>
                  )}
                </Radio.Group>
                {aiAssisted ? (
                  <div
                    className={`${styles.full} rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] p-4`}
                    data-testid='template-ai-assistant'
                  >
                    <div className='mb-2 flex items-center gap-2 font-semibold'>
                      <CommentOutlined />
                      模板 AI 助手
                    </div>
                    <p className='mb-3 text-sm leading-6 text-[var(--app-muted)]'>
                      {features ? '已提取模板的组件组合、布局和配色。' : '将使用所选模板的组件组合、布局和配色。'}AI
                      会匹配你的数据；缺少字段时调整指标与图表，并验证实际查询结果。
                    </p>
                    <div className='mb-3 flex flex-wrap gap-1'>
                      {features?.widgets.map(widget => <Tag key={widget.id}>{widget.title}</Tag>)}
                    </div>
                    <details open>
                      <summary className='mb-2 cursor-pointer text-sm'>从模板提取的生成要求</summary>
                      <Input.TextArea
                        aria-label='模板 AI 生成要求'
                        maxLength={6000}
                        value={aiPrompt}
                        disabled={busy}
                        autoSize={{ minRows: 4, maxRows: 8 }}
                        onChange={event => {
                          setAiPrompt(event.target.value);
                          epoch.current++;
                          setPreview(null);
                        }}
                      />
                    </details>
                    {busy && (
                      <div className='mt-3 flex items-center gap-2 text-xs text-[var(--app-muted)]' role='status'>
                        <Spin size='small' />
                        正在匹配字段、调整图表并验证查询…
                      </div>
                    )}
                  </div>
                ) : !manual ? (
                  <Alert
                    className={styles.full}
                    type='info'
                    showIcon
                    message='已找到模板适配的表结构'
                    description='此数据源包含模板预置适配所需的数据表。点击“验证并预览”检查查询与筛选结果；字段或业务粒度不同，可切换到“手动匹配字段”。预览确认后才会创建看板。'
                  />
                ) : (
                  <>
                    <Alert
                      className={styles.full}
                      type='info'
                      showIcon
                      message={`手动匹配：已完成 ${requiredRoles.length - missingRoles.length}/${requiredRoles.length} 个必填字段`}
                      description={
                        <>
                          <p>先选业务明细表，再为模板指标选择含义相同的字段，最后确认单位和每行数据的业务含义。</p>
                          <p>
                            手动匹配沿用模板的指标含义。数据里没有对应字段时（例如销售数据没有年龄、血压），请使用 AI
                            智能适配，让指标随真实数据调整，或选择相同业务的模板。
                          </p>
                          <Button
                            size='small'
                            disabled={busy}
                            onClick={() => {
                              epoch.current++;
                              setAiAssisted(true);
                              setPreview(null);
                              setError('');
                            }}
                          >
                            缺少对应字段，改用 AI 智能适配
                          </Button>
                        </>
                      }
                    />
                    <label>
                      业务明细表
                      <Select
                        aria-label='业务明细表'
                        placeholder='第 1 步：选择存放业务记录的数据表'
                        value={mapping.table || undefined}
                        disabled={busy}
                        showSearch
                        options={info.tables.map(t => ({ label: t.name, value: t.name }))}
                        onChange={table => {
                          setConfirmedGrain(false);
                          editMapping({ table, fields: {}, joins: [] });
                        }}
                      />
                      <small>
                        {info.tables.length === 1
                          ? '此数据源只有一张表，已自动选中；请继续匹配下面的字段。'
                          : '选择一行代表一条业务记录的表；字段选择只显示这张表及已添加的关联表。'}
                      </small>
                    </label>
                    <label>
                      日期格式
                      <Select
                        aria-label='日期格式'
                        disabled={busy}
                        value={mapping.date_format}
                        options={[
                          { value: 'iso', label: '年-月-日 / ISO 时间' },
                          { value: 'dmy', label: '日-月-年（DD-MM-YYYY）' },
                        ]}
                        onChange={date_format => editMapping({ date_format })}
                      />
                    </label>
                    <Collapse
                      className={styles.full}
                      items={[
                        {
                          key: 'joins',
                          label: `关联分类表（可选，${mapping.joins.length}/3）`,
                          children: (
                            <div className={styles.joins}>
                              <p>
                                从明细表连接唯一键，不合并重复键。需要一对多或多个事实表时，请先整理为所需明细粒度。
                              </p>
                              {mapping.joins.map((join, i) => (
                                <div className={styles.join} key={i}>
                                  <Select
                                    aria-label={`关联 ${i + 1} 左侧字段`}
                                    placeholder='左侧字段'
                                    disabled={busy}
                                    options={fieldOptions([
                                      mapping.table,
                                      ...mapping.joins.slice(0, i).map(j => j.table),
                                    ])}
                                    value={fieldValue(join.left)}
                                    onChange={v => updateJoin(i, { left: JSON.parse(v) })}
                                  />
                                  <Select
                                    aria-label={`关联 ${i + 1} 数据表`}
                                    placeholder='分类表'
                                    disabled={busy}
                                    options={info.tables
                                      .filter(t => t.name !== mapping.table)
                                      .map(t => ({ label: t.name, value: t.name }))}
                                    value={join.table || undefined}
                                    onChange={table => updateJoin(i, { table, right_column: '' })}
                                  />
                                  <Select
                                    aria-label={`关联 ${i + 1} 唯一键`}
                                    placeholder='分类表唯一键'
                                    disabled={busy}
                                    options={info.tables
                                      .find(t => t.name === join.table)
                                      ?.columns.map(c => ({ value: c.name, label: c.name }))}
                                    value={join.right_column || undefined}
                                    onChange={right_column => updateJoin(i, { right_column })}
                                  />
                                  <Button
                                    aria-label={`移除关联 ${i + 1}`}
                                    icon={<DeleteOutlined />}
                                    disabled={busy}
                                    onClick={() =>
                                      editMapping({ joins: mapping.joins.filter((_, n) => n !== i), fields: {} })
                                    }
                                  />
                                </div>
                              ))}
                              <Button
                                icon={<PlusOutlined />}
                                disabled={!mapping.table || busy || mapping.joins.length >= 3}
                                onClick={() =>
                                  editMapping({
                                    joins: [
                                      ...mapping.joins,
                                      { table: '', left: { table: '', column: '' }, right_column: '' },
                                    ],
                                  })
                                }
                              >
                                添加关联
                              </Button>
                            </div>
                          ),
                        },
                      ]}
                    />
                    {info.roles
                      .filter(r => r.required || ['value', 'entity'].includes(r.id))
                      .map(role => (
                        <label key={role.id}>
                          {role.label}
                          {role.required ? ' *' : '（可选）'}
                          <Select
                            aria-label={`匹配${role.label}`}
                            placeholder={
                              mapping.table ? `选择含义对应“${role.label}”的字段` : '请先选择上方的业务明细表'
                            }
                            disabled={busy || !mapping.table}
                            showSearch
                            optionFilterProp='label'
                            allowClear
                            value={fieldValue(mapping.fields[role.id])}
                            options={fieldOptions()}
                            onChange={value => {
                              const fields = { ...mapping.fields };
                              if (value) fields[role.id] = JSON.parse(value);
                              else delete fields[role.id];
                              editMapping({ fields });
                            }}
                          />
                          <small>{role.hint}</small>
                        </label>
                      ))}
                    <label>
                      主要数值单位
                      <Input
                        aria-label='主要数值单位'
                        disabled={busy}
                        placeholder='例如：元、美元、次；纯计数模板填“条”'
                        maxLength={32}
                        value={mapping.unit}
                        onChange={e => editMapping({ unit: e.target.value })}
                      />
                    </label>
                    {template.id === 'northwind-customers' && (
                      <label>
                        留存观察周期
                        <Select
                          aria-label='留存观察周期'
                          disabled={busy}
                          value={mapping.interval}
                          options={[
                            { value: 'week', label: '按周（周一开始）' },
                            { value: 'month', label: '按自然月' },
                          ]}
                          onChange={interval => editMapping({ interval })}
                        />
                      </label>
                    )}
                    <Checkbox
                      className={styles.full}
                      checked={confirmedGrain}
                      disabled={busy}
                      onChange={e => setConfirmedGrain(e.target.checked)}
                    >
                      我确认明细表每行代表{grainLabels[info.grain]}，主要数值与所填单位一致。
                    </Checkbox>
                  </>
                )}
              </>
            )
          )}
        </div>
      )}
    </Modal>
  );
}
