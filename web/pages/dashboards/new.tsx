import { ChatContext } from '@/app/chat-context';
import { getDbList } from '@/client/api';
import useChat from '@/hooks/use-chat';
import { SELECTED_MODEL_STORAGE_KEY } from '@/lib/model-runtime';
import QuestionDock from '@/new-components/chat/content/QuestionDock';
import DashboardGenerationCard, { DashboardGenerationState } from '@/new-components/dashboard/DashboardGenerationCard';
import { reduceDashboardGenerations } from '@/new-components/dashboard/dashboard-generation-state';
import type { IChatDbSchema } from '@/types/db';
import { getUserId } from '@/utils';
import { Alert, Button, Input, Select, Space } from 'antd';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useContext, useEffect, useRef, useState } from 'react';

type DataSource = { db_name: string; db_type: string };

function dashboardSource(source: IChatDbSchema): DataSource {
  return {
    db_name: source.db_name || source.params?.name || '',
    db_type: source.type || source.db_type || '',
  };
}

/** A scoped entry to the existing planning/confirmation workflow. */
export default function DashboardCreatePage() {
  const router = useRouter();
  const { model, modelList } = useContext(ChatContext);
  const { chat, pendingQuestion, replyQuestion, rejectQuestion } = useChat({});
  const [sources, setSources] = useState<DataSource[]>([]);
  const [sourceName, setSourceName] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const effectiveModel = selectedModel || (modelList.includes(model) ? model : modelList[0]) || '';
  const [files, setFiles] = useState<File[]>([]);
  const [prompt, setPrompt] = useState('');
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [generations, setGenerations] = useState<DashboardGenerationState[]>([]);
  const active = useRef<AbortController | null>(null);
  const conversationId = useRef('');
  const datasetId = useRef('');
  const textInput = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let disposed = false;
    void getDbList()
      .then(response => {
        if (!response.data.success) throw new Error(response.data.err_msg || '数据源加载失败');
        if (!disposed) {
          setSources(
            (response.data.data || []).map(dashboardSource).filter(source => source.db_name && source.db_type),
          );
        }
      })
      .catch(cause => {
        if (!disposed) setError(cause instanceof Error ? cause.message : '数据源加载失败，请刷新后重试');
      });
    return () => {
      disposed = true;
      active.current?.abort();
    };
  }, []);

  const send = async (input: string) => {
    if (active.current || !input.trim()) return;
    const source = sources.find(item => item.db_name === sourceName);
    if (!effectiveModel || (!source && !files.length && !datasetId.current)) {
      setError('请选择可用模型，以及一个数据源或 CSV / Excel 文件。');
      return;
    }
    const controller = new AbortController();
    active.current = controller;
    conversationId.current ||= crypto.randomUUID();
    setBusy(true);
    setError('');
    setAnswer('');
    setHasRun(true);
    localStorage.setItem(SELECTED_MODEL_STORAGE_KEY, effectiveModel);
    const complete = () => {
      if (active.current === controller) {
        active.current = null;
        setBusy(false);
      }
      controller.abort();
    };
    try {
      if (files.length && !datasetId.current) {
        const form = new FormData();
        files.forEach(file => form.append('files', file));
        form.append('conv_uid', conversationId.current);
        const upload = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/python/files/upload`, {
          method: 'POST',
          headers: { 'User-Id': getUserId() || '' },
          body: form,
          signal: controller.signal,
        });
        const body = await upload.json();
        if (!upload.ok || !body.success || !body.data?.dataset_id) {
          throw new Error(body.err_msg || '文件上传失败，文件已保留，可重新发送');
        }
        datasetId.current = body.data.dataset_id;
      }
      controller.signal.throwIfAborted();
      await chat({
        chatId: conversationId.current,
        ctrl: controller,
        data: {
          chat_mode: 'chat_react_agent',
          model_name: effectiveModel,
          select_param: '',
          user_input: input,
          temperature: 0.3,
          max_new_tokens: 4000,
          ext_info: {
            creation_mode: 'dashboard',
            ...(datasetId.current
              ? { dataset_id: datasetId.current }
              : {
                  database_name: source!.db_name,
                  database_type: source!.db_type,
                }),
          },
        },
        onMessage: content => {
          setAnswer(previous => (content.startsWith(previous) ? content : previous + content));
        },
        onDashboardEvent: event => setGenerations(previous => reduceDashboardGenerations(previous, event)),
        onDone: complete,
        onError: (detail, cause) => {
          setError(cause?.message || detail);
          complete();
        },
      });
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '生成失败，请重试');
    } finally {
      if (active.current === controller) {
        active.current = null;
        setBusy(false);
      }
    }
  };

  const stop = () => {
    active.current?.abort();
    active.current = null;
    setBusy(false);
    setError('已停止生成。已有规划和草稿仍保留，可修改需求后继续。');
  };

  return (
    <main className='h-full overflow-auto p-4 md:p-8'>
      <Head>
        <title>新建看板 · DB-GPT</title>
      </Head>
      <div className='mx-auto max-w-4xl space-y-5'>
        <div className='flex items-center justify-between gap-4'>
          <div>
            <h1 className='text-xl font-semibold'>新建看板</h1>
            <p className='mt-2 text-sm text-gray-500'>选择数据，描述要分析的问题，确认计划后生成图表。</p>
          </div>
          <Link href='/dashboards'>返回看板列表</Link>
        </div>
        {error && <Alert type='warning' showIcon message={error} />}
        <div className='grid gap-4 md:grid-cols-2'>
          <label className='flex flex-col gap-2'>
            数据源
            <Select
              aria-label='数据源'
              value={sourceName || undefined}
              placeholder='请选择数据源'
              disabled={busy || hasRun || files.length > 0}
              options={sources.map(source => ({ value: source.db_name, label: source.db_name }))}
              onChange={setSourceName}
            />
          </label>
          <label className='flex flex-col gap-2'>
            模型
            <Select
              aria-label='模型'
              value={effectiveModel || undefined}
              placeholder='请选择模型'
              disabled={busy}
              options={modelList.map(value => ({ value, label: value }))}
              onChange={setSelectedModel}
            />
          </label>
        </div>
        <label className='flex flex-col gap-2 text-sm'>
          或上传 CSV / Excel 文件（可多选）
          <input
            aria-label='上传数据文件'
            type='file'
            multiple
            accept='.csv,.xlsx,.xls'
            disabled={busy || hasRun}
            onChange={event => {
              setFiles(Array.from(event.target.files || []));
              setSourceName('');
            }}
          />
        </label>
        {generations.map((generation, index) => (
          <DashboardGenerationCard
            key={generation.dashboardId || index}
            state={generation}
            busy={busy}
            onOpen={() =>
              generation.dashboardId && void router.push(`/dashboards/${encodeURIComponent(generation.dashboardId)}`)
            }
            onConfirm={state => {
              if (state.confirmationPrompt) void send(state.confirmationPrompt);
            }}
            onRevise={() => {
              setPrompt(generation.revisionPrompt || '请修改看板计划：');
              textInput.current?.focus();
            }}
          />
        ))}
        {answer && (
          <div
            role='log'
            aria-label='看板生成答复'
            className='whitespace-pre-wrap break-words rounded-lg border border-gray-200 p-4'
          >
            {answer}
          </div>
        )}
        {pendingQuestion && busy && (
          <QuestionDock request={pendingQuestion} onReply={replyQuestion} onReject={rejectQuestion} />
        )}
        <form
          onSubmit={event => {
            event.preventDefault();
            void send(prompt);
          }}
          className='space-y-3'
        >
          <label className='flex flex-col gap-2'>
            分析需求
            <Input.TextArea
              aria-label='分析需求'
              ref={element => {
                textInput.current = element?.resizableTextArea?.textArea || null;
              }}
              rows={4}
              value={prompt}
              disabled={busy}
              onChange={event => setPrompt(event.target.value)}
              placeholder='例如：分析门店月度销售额、增长趋势和排名，并增加日期筛选。'
            />
          </label>
          <Space wrap>
            <Button htmlType='submit' type='primary' loading={busy} disabled={!prompt.trim() || busy}>
              发送需求
            </Button>
            {busy && <Button onClick={stop}>停止生成</Button>}
            {hasRun && !busy && (
              <Button
                onClick={() => {
                  conversationId.current = '';
                  datasetId.current = '';
                  setHasRun(false);
                  setGenerations([]);
                  setAnswer('');
                  setError('');
                }}
              >
                开始新看板
              </Button>
            )}
          </Space>
        </form>
      </div>
    </main>
  );
}
