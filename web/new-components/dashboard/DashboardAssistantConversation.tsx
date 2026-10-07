import type { DashboardAnnotationRecord } from '@/types/dashboard';
import { CloseOutlined, CommentOutlined, EditOutlined, SendOutlined, StopOutlined } from '@ant-design/icons';
import { Button, Input, Spin } from 'antd';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import type { DashboardAnnotationDraft } from './dashboard-assistant';
import type { AssistantMessage, SavedDashboardAnnotation } from './dashboard-assistant-session';
import styles from './DashboardAssistantPanel.module.css';

export default function DashboardAssistantConversation({
  messages,
  running,
  status,
  onSend,
  onStop,
  onRetry,
  onShowAnnotations,
  savedCount,
  proposals,
  applying,
  onApplyBatch,
  onPreview,
  question,
  attachments,
  onEditAttachment,
  onRemoveAttachment,
  onLocateAnnotation,
}: {
  messages: AssistantMessage[];
  running: boolean;
  status: string;
  onSend: (text: string) => void;
  onStop: () => void;
  onRetry: () => void;
  onShowAnnotations: () => void;
  savedCount: number;
  proposals: DashboardAnnotationRecord[];
  applying: boolean;
  onApplyBatch: () => void;
  onPreview: (proposal: DashboardAnnotationRecord) => void;
  question?: ReactNode;
  attachments: SavedDashboardAnnotation[];
  onEditAttachment: (draft: DashboardAnnotationDraft) => void;
  onRemoveAttachment: (id: string) => void;
  onLocateAnnotation: (draft: DashboardAnnotationDraft) => void;
}) {
  const [input, setInput] = useState('');
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'nearest' });
  }, [messages, status]);
  const send = () => {
    if ((!input.trim() && !attachments.length) || running) return;
    onSend(input.trim());
    setInput('');
  };
  return (
    <div className={styles.panel} data-testid='dashboard-assistant-panel'>
      <div className={styles.messages} role='log' aria-label='看板 AI 对话' aria-live='polite'>
        {!messages.length && (
          <div className={styles.empty}>
            <strong>一起完善这个看板</strong>
            <p>在图表上保存批注，准备好后一起发送。也可以直接在这里提问、补充要求。</p>
            {!!savedCount && <Button onClick={onShowAnnotations}>查看本次 {savedCount} 条批注</Button>}
          </div>
        )}
        {messages.map((item, index) => (
          <article
            key={item.id}
            className={item.role === 'user' ? styles.userMessage : styles.assistantMessage}
            data-message-role={item.role}
          >
            <div className={styles.author}>{item.role === 'user' ? '你' : 'AI 助手'}</div>
            <ReactMarkdown>{item.content}</ReactMarkdown>
            {!!item.annotations?.length && (
              <details className={styles.messageAttachments}>
                <summary>
                  <CommentOutlined /> {item.annotations.length} 条批注
                </summary>
                {item.annotations.map((annotation, annotationIndex) => (
                  <button key={annotation.id} type='button' onClick={() => onLocateAnnotation(annotation)}>
                    <strong>
                      {annotationIndex + 1}. {annotation.target.label}
                    </strong>
                    <small>{annotation.chartType}</small>
                    <span>{annotation.content}</span>
                  </button>
                ))}
              </details>
            )}
            {item.failed && !running && index === messages.length - 1 && (
              <Button size='small' onClick={onRetry}>
                重试这次请求
              </Button>
            )}
          </article>
        ))}
        {running && (
          <div className={styles.status} role='status'>
            <Spin size='small' />
            <span>{status || '正在处理…'}</span>
          </div>
        )}
        {!!proposals.length && (
          <details className={styles.annotation}>
            <summary>{proposals.length} 项修改待确认</summary>
            {proposals.map(item => (
              <div key={item.id} className='my-3'>
                <p>{item.proposal?.summary || item.target.label}</p>
                <Button size='small' onClick={() => onPreview(item)}>
                  查看修改
                </Button>
              </div>
            ))}
            <Button block type='primary' disabled={running} loading={applying} onClick={onApplyBatch}>
              应用本批修改
            </Button>
          </details>
        )}
        {question}
        <div ref={end} />
      </div>
      <div className={styles.composer}>
        {!!attachments.length && (
          <div className={styles.attachments} data-testid='annotation-composer-attachments'>
            <div className={styles.attachmentHeading}>
              <span>
                <CommentOutlined /> {attachments.length} 条批注随消息发送
              </span>
              <button type='button' onClick={onShowAnnotations}>
                本次记录
              </button>
            </div>
            <div className={styles.attachmentList}>
              {attachments.map((item, index) => (
                <div key={item.id} className={styles.attachment} data-testid='annotation-composer-item'>
                  <button className={styles.attachmentContent} type='button' onClick={() => onLocateAnnotation(item)}>
                    <strong>
                      {index + 1}. {item.target.label}
                    </strong>
                    <small>
                      {item.chartType}
                      {item.state === 'discussing' ? ' · 等待补充' : ''}
                    </small>
                    <span>{item.content}</span>
                  </button>
                  <div>
                    <Button
                      size='small'
                      type='text'
                      icon={<EditOutlined />}
                      disabled={running}
                      aria-label={`编辑 ${item.target.label} 批注`}
                      onClick={() => onEditAttachment(item)}
                    />
                    <Button
                      size='small'
                      type='text'
                      icon={<CloseOutlined />}
                      disabled={running}
                      aria-label={`移除 ${item.target.label} 批注`}
                      onClick={() => onRemoveAttachment(item.id)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        <Input.TextArea
          aria-label='给看板 AI 助手发消息'
          placeholder={attachments.length ? '补充这批修改的要求，或直接发送批注…' : '补充要求，或继续讨论这个看板…'}
          maxLength={2000}
          autoSize={{ minRows: 3, maxRows: 7 }}
          value={input}
          onChange={event => setInput(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              send();
            }
          }}
        />
        <div className={styles.composerActions}>
          <span>Enter 发送 · Shift + Enter 换行</span>
          {running ? (
            <Button aria-label='停止 AI 回复' icon={<StopOutlined />} onClick={onStop} />
          ) : (
            <Button
              type='primary'
              aria-label='发送消息'
              icon={<SendOutlined />}
              disabled={!input.trim() && !attachments.length}
              onClick={send}
            />
          )}
        </div>
      </div>
    </div>
  );
}
