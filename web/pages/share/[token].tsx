/**
 * /share/[token] — Conversation replay page
 *
 * Fetches shared conversation data from the backend and animates each round
 * through think → act → output. No login required; read-only; cannot continue chatting.
 */

import ManusLeftPanel, {
  ArtifactItem,
  ExecutionStep as ManusExecutionStep,
  StepType,
  ThinkingSection,
} from '@/new-components/chat/content/ManusLeftPanel';
import ManusRightPanel, {
  ActiveStepInfo,
  ExecutionOutput as ManusExecutionOutput,
  PanelView,
} from '@/new-components/chat/content/ManusRightPanel';
import {
  LinkOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  StepForwardOutlined,
} from '@ant-design/icons';
import { Button, Tooltip, message } from 'antd';
import { NextPage } from 'next';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// ---------------------------------------------------------------------------
// Types mirroring index.tsx
// ---------------------------------------------------------------------------

interface RawStep {
  id: string;
  title?: string;
  detail?: string;
  thought?: string;
  action?: string;
  action_input?: any;
  outputs?: Array<{ output_type: string; content: any }>;
  status?: string;
}

interface RawPayload {
  version: number;
  type: string;
  final_content: string;
  steps: RawStep[];
  generated_images?: string[];
}

interface _ParsedMessage {
  role: 'human' | 'view';
  context: string;
  order: number;
  payload?: RawPayload; // only for view messages with react-agent payload
}

/** A fully prepared "round" ready for the replay engine */
interface ReplayRound {
  humanText: string;
  steps: ManusExecutionStep[];
  outputs: Record<string, ManusExecutionOutput[]>;
  stepThoughts: Record<string, string>;
  finalContent: string;
  artifacts: ArtifactItem[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const getStepType = (title?: string): StepType => {
  const lower = (title || '').toLowerCase();
  if (lower.includes('load_skill') || lower.includes('load skill')) return 'skill';
  if (lower.includes('sql_query') || lower.includes('sql query') || lower.includes('sql')) return 'sql';
  if (lower.includes('read') || lower.includes('load')) return 'read';
  if (lower.includes('edit')) return 'edit';
  if (lower.includes('write') || lower.includes('save')) return 'write';
  if (lower.includes('bash') || lower.includes('execute') || lower.includes('command')) return 'bash';
  if (lower.includes('grep') || lower.includes('search')) return 'grep';
  if (lower.includes('glob') || lower.includes('find')) return 'glob';
  if (lower.includes('html')) return 'html';
  if (lower.includes('python') || lower.includes('code')) return 'python';
  if (lower.includes('skill')) return 'skill';
  if (lower.includes('task')) return 'task';
  return 'other';
};

/** Extract ArtifactItem[] from a round's steps+outputs (mirrors index.tsx buildArtifactsFromExecution) */
function buildArtifacts(
  roundId: string,
  steps: ManusExecutionStep[],
  outputs: Record<string, ManusExecutionOutput[]>,
  finalContent: string,
): ArtifactItem[] {
  const artifacts: ArtifactItem[] = [];
  const now = Date.now();
  const seenCodeHashes = new Set<string>();

  steps.forEach(step => {
    const stepOutputs = outputs[step.id] || [];
    stepOutputs.forEach((output, oIdx) => {
      if (output.output_type === 'code') {
        const codeStr = String(output.content || '').trim();
        const hash = codeStr.slice(0, 200);
        if (codeStr && !seenCodeHashes.has(hash)) {
          seenCodeHashes.add(hash);
          artifacts.push({
            id: `${roundId}-code-${step.id}-${oIdx}`,
            type: 'code',
            name: `code_${oIdx + 1}.py`,
            content: codeStr,
            createdAt: now,
            downloadable: true,
          });
        }
      } else if ((output.output_type as string) === 'file') {
        artifacts.push({
          id: `${roundId}-file-${step.id}-${oIdx}`,
          type: 'file',
          name: output.content?.name || output.content?.file_name || 'File',
          content: output.content,
          createdAt: now,
          downloadable: true,
          size: output.content?.size,
        });
      } else if (output.output_type === 'html') {
        const htmlContent =
          typeof output.content === 'string'
            ? output.content
            : output.content?.content || output.content?.html || String(output.content);
        const htmlTitle = output.content?.title || 'Report';
        artifacts.push({
          id: `${roundId}-html-${step.id}-${oIdx}`,
          type: 'html',
          name: `${htmlTitle}.html`,
          content: htmlContent,
          createdAt: now,
          downloadable: true,
        });
      } else if (output.output_type === 'image') {
        const imgUrl =
          typeof output.content === 'string'
            ? output.content
            : output.content?.url || output.content?.src || String(output.content);
        const imgName = imgUrl.split('/').pop() || `image_${oIdx}.png`;
        artifacts.push({
          id: `${roundId}-img-${step.id}-${oIdx}`,
          type: 'image',
          name: imgName.replace(/^[a-f0-9]{8}_/, ''),
          content: imgUrl,
          createdAt: now,
          downloadable: true,
        });
      }
    });
  });

  // Also scan final_content for file references (e.g. "saved to xxx.xlsx")
  const fileRefRegex = /[\w\u4e00-\u9fa5_-]+\.(xlsx?|csv|pdf|png|jpg|jpeg|gif|html?|txt|zip|json)/gi;
  const matches = finalContent.matchAll(fileRefRegex);
  for (const m of matches) {
    const name = m[0];
    if (!artifacts.some(a => a.name.toLowerCase() === name.toLowerCase())) {
      artifacts.push({
        id: `${roundId}-fileref-${name}`,
        type: 'file',
        name,
        content: { name },
        createdAt: now,
        downloadable: true,
      });
    }
  }

  return artifacts;
}

/** Build ReplayRound[] from raw messages returned by the share API */
function buildReplayRounds(rawMessages: Array<{ role: string; context: string; order: number }>): ReplayRound[] {
  const rounds: ReplayRound[] = [];
  let pendingHuman: string | null = null;

  for (const msg of rawMessages) {
    if (msg.role === 'human') {
      pendingHuman = msg.context;
    } else if (msg.role === 'view') {
      let payload: RawPayload | null = null;
      try {
        const parsed = JSON.parse(msg.context);
        if (parsed?.version === 1 && parsed?.type === 'react-agent') {
          payload = parsed as RawPayload;
        }
      } catch {
        /* ignore */
      }

      if (!payload) continue;

      const steps: ManusExecutionStep[] = [];
      const outputs: Record<string, ManusExecutionOutput[]> = {};
      const stepThoughts: Record<string, string> = {};

      (payload.steps || []).forEach((s, idx) => {
        const stepId = s.id || `step-${idx}`;
        // Filter terminate steps
        if ((s.detail || '').toLowerCase().includes('action: terminate')) return;

        steps.push({
          id: stepId,
          type: getStepType(s.title),
          title: s.title || `Step ${idx + 1}`,
          subtitle: (s.detail || '').split('\n')[0]?.slice(0, 80),
          description: s.detail || undefined,
          status: s.status === 'failed' ? 'error' : 'completed',
        });

        const stepOutputs: ManusExecutionOutput[] = [];
        // Prepend code from action_input for code_interpreter steps
        if (s.action === 'code_interpreter' && s.action_input) {
          try {
            const inp = typeof s.action_input === 'string' ? JSON.parse(s.action_input) : s.action_input;
            if (inp?.code) stepOutputs.push({ output_type: 'code', content: inp.code });
          } catch {
            /* ignore */
          }
        }
        if (Array.isArray(s.outputs)) {
          s.outputs.forEach(o => stepOutputs.push({ output_type: o.output_type as any, content: o.content }));
        }
        outputs[stepId] = stepOutputs;
        if (s.thought) stepThoughts[stepId] = s.thought;
      });

      const artifacts = buildArtifacts(`round-${rounds.length}`, steps, outputs, payload.final_content || '');
      rounds.push({
        humanText: pendingHuman || '',
        steps,
        outputs,
        stepThoughts,
        finalContent: payload.final_content || '',
        artifacts,
      });
      pendingHuman = null;
    }
  }

  return rounds;
}

/** Build ThinkingSection[] from a round's steps (same grouping logic as index.tsx) */
function buildSections(steps: ManusExecutionStep[]): ThinkingSection[] {
  if (steps.length === 0) return [];

  const thinkSteps = steps.filter(
    s => s.title?.toLowerCase().includes('think') || s.title?.toLowerCase().includes('plan'),
  );
  const skillSteps = steps.filter(s => s.title?.toLowerCase().includes('skill'));
  const otherSteps = steps.filter(
    s =>
      !s.title?.toLowerCase().includes('think') &&
      !s.title?.toLowerCase().includes('plan') &&
      !s.title?.toLowerCase().includes('skill'),
  );

  const sections: ThinkingSection[] = [];
  if (thinkSteps.length > 0)
    sections.push({ id: 'section-think', title: 'Analysis & Planning', isCompleted: true, steps: thinkSteps });
  if (skillSteps.length > 0)
    sections.push({ id: 'section-skill', title: 'Skill Loading', isCompleted: true, steps: skillSteps });
  if (otherSteps.length > 0)
    sections.push({
      id: 'section-execution',
      title: 'Data Processing & Execution',
      isCompleted: true,
      steps: otherSteps,
    });
  if (sections.length === 0) sections.push({ id: 'section-main', title: 'Execution', isCompleted: true, steps });
  return sections;
}

// ---------------------------------------------------------------------------
// Replay speed config
// ---------------------------------------------------------------------------

const SPEED_OPTIONS = [
  { label: '0.5×', value: 0.5 },
  { label: '1×', value: 1 },
  { label: '2×', value: 2 },
  { label: '4×', value: 4 },
];

/** Delays (ms) per event at 1× speed */
const BASE_DELAYS = {
  beforeStep: 600, // pause before revealing a step
  afterStep: 400, // pause after a step appears before showing outputs
  betweenOutputs: 300,
  beforeFinal: 700,
  betweenRounds: 1000,
};

// ---------------------------------------------------------------------------
// useReplayEngine hook
// ---------------------------------------------------------------------------

/** Represents the visible state at any instant during replay */
interface ReplayState {
  /** Which round index is currently showing (0-based) */
  roundIndex: number;
  /** Steps revealed so far in the current round (all previous rounds are fully shown) */
  visibleStepCount: number;
  /** The step currently "active" (highlighted in the right panel) */
  activeStepId: string | null;
  /** Whether we are showing the final summary for the current round */
  showFinalForRound: boolean;
  /** Index of the last fully-finished round */
  completedRoundIndex: number;
  /** Whether replay has finished */
  done: boolean;
}

function useReplayEngine(rounds: ReplayRound[], speed: number, autoPlay = false) {
  const [state, setState] = useState<ReplayState>({
    roundIndex: 0,
    visibleStepCount: 0,
    activeStepId: null,
    showFinalForRound: false,
    completedRoundIndex: -1,
    done: false,
  });
  const [playing, setPlaying] = useState(false);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const playingRef = useRef(playing);
  playingRef.current = playing;
  const speedRef = useRef(speed);
  speedRef.current = speed;
  const roundsRef = useRef(rounds);
  roundsRef.current = rounds;

  const delay = useCallback((ms: number) => {
    return new Promise<void>(resolve => {
      timerRef.current = setTimeout(resolve, ms / speedRef.current);
    });
  }, []);

  const runLoop = useCallback(async () => {
    const currentRounds = roundsRef.current;
    const startRound = stateRef.current.roundIndex;
    const startStep = stateRef.current.visibleStepCount;

    for (let ri = startRound; ri < currentRounds.length; ri++) {
      const round = currentRounds[ri];
      const siStart = ri === startRound ? startStep : 0;

      for (let si = siStart; si < round.steps.length; si++) {
        if (!playingRef.current) return;

        const step = round.steps[si];
        await delay(BASE_DELAYS.beforeStep);
        if (!playingRef.current) return;

        setState(prev => ({
          ...prev,
          roundIndex: ri,
          visibleStepCount: si + 1,
          activeStepId: step.id,
          showFinalForRound: false,
        }));

        await delay(BASE_DELAYS.afterStep);
        if (!playingRef.current) return;
      }

      await delay(BASE_DELAYS.beforeFinal);
      if (!playingRef.current) return;

      setState(prev => ({
        ...prev,
        roundIndex: ri,
        visibleStepCount: round.steps.length,
        activeStepId: round.steps.length > 0 ? round.steps[round.steps.length - 1].id : null,
        showFinalForRound: true,
        completedRoundIndex: ri,
      }));

      if (ri < currentRounds.length - 1) {
        await delay(BASE_DELAYS.betweenRounds);
        if (!playingRef.current) return;
        setState(prev => ({
          ...prev,
          roundIndex: ri + 1,
          visibleStepCount: 0,
          activeStepId: null,
          showFinalForRound: false,
        }));
      }
    }

    setState(prev => ({ ...prev, done: true }));
    setPlaying(false);
  }, [delay]);

  const play = useCallback(() => {
    if (stateRef.current.done) return;
    setPlaying(true);
  }, []);

  const pause = useCallback(() => {
    setPlaying(false);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  // Start/resume loop when playing becomes true
  useEffect(() => {
    if (playing) {
      runLoop();
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [playing, runLoop]);

  // Auto-play when rounds become available
  useEffect(() => {
    if (autoPlay && rounds.length > 0 && !playingRef.current && !stateRef.current.done) {
      setPlaying(true);
    }
  }, [autoPlay, rounds.length]);

  /** Jump to a specific round (skips to its end instantly) */
  const jumpToRound = useCallback(
    (ri: number) => {
      pause();
      setState({
        roundIndex: ri,
        visibleStepCount: rounds[ri]?.steps.length ?? 0,
        activeStepId: rounds[ri]?.steps.slice(-1)[0]?.id ?? null,
        showFinalForRound: true,
        completedRoundIndex: ri,
        done: ri === rounds.length - 1,
      });
    },
    [pause, rounds],
  );

  /** Restart replay from the beginning */
  const restart = useCallback(() => {
    pause();
    setState({
      roundIndex: 0,
      visibleStepCount: 0,
      activeStepId: null,
      showFinalForRound: false,
      completedRoundIndex: -1,
      done: false,
    });
    // Small delay to let state settle before starting loop
    setTimeout(() => setPlaying(true), 50);
  }, [pause]);

  return { state, playing, play, pause, jumpToRound, restart };
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

const SharePage: NextPage = () => {
  const router = useRouter();
  const { token } = router.query as { token?: string };

  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Array<{ role: string; context: string; order: number }> | null>(null);
  const [firstQuestion, setFirstQuestion] = useState<string>('');
  const [speed, setSpeed] = useState(1);
  const [rightPanelView, setRightPanelView] = useState<PanelView>('execution');

  useEffect(() => {
    if (!token) return;
    const apiBase = process.env.API_BASE_URL ?? '';
    setLoading(true);
    fetch(`${apiBase}/api/v1/chat/share/${token}`)
      .then(res => {
        if (!res.ok) {
          setFetchError(`Share link is invalid or expired (${res.status})`);
          setLoading(false);
          return null;
        }
        return res.json();
      })
      .then(json => {
        if (!json) return;
        const rawMessages = json?.data?.messages ?? null;
        if (!Array.isArray(rawMessages)) {
          setFetchError('Invalid data format');
          setLoading(false);
          return;
        }
        setMessages(rawMessages);
        setFirstQuestion(rawMessages.find((m: any) => m.role === 'human')?.context ?? '');
        setLoading(false);
      })
      .catch((err: any) => {
        setFetchError(err?.message || 'Failed to load');
        setLoading(false);
      });
  }, [token]);

  const rounds = useMemo(() => (messages ? buildReplayRounds(messages) : []), [messages]);
  const { state, playing, play, pause, jumpToRound, restart } = useReplayEngine(
    rounds,
    speed,
    !loading && rounds.length > 0,
  );

  // -------------------------------------------------------------------------
  // Derive display data from replay state
  // -------------------------------------------------------------------------

  /** For each round index, compute what's visible */
  const getVisibleRoundData = (ri: number) => {
    const round = rounds[ri];
    if (!round) return null;

    const isCurrentRound = ri === state.roundIndex;
    const isCompletedRound = ri < state.roundIndex || (ri === state.roundIndex && state.showFinalForRound);

    const visibleSteps: ManusExecutionStep[] = isCurrentRound
      ? round.steps.slice(0, state.visibleStepCount).map((s, idx) => ({
          ...s,
          status: idx < state.visibleStepCount - 1 ? 'completed' : playing ? 'running' : 'completed',
        }))
      : isCompletedRound
        ? round.steps.map(s => ({ ...s, status: 'completed' as const }))
        : [];

    const sections = buildSections(visibleSteps);
    const showFinal = isCompletedRound || (isCurrentRound && state.showFinalForRound);
    const activeStepId = isCurrentRound
      ? state.activeStepId
      : isCompletedRound
        ? (round.steps.slice(-1)[0]?.id ?? null)
        : null;

    return { round, visibleSteps, sections, showFinal, activeStepId };
  };

  // Active round for the right panel
  const activeRoundData = getVisibleRoundData(state.roundIndex);
  const activeStepId = state.activeStepId;

  const rightPanelOutputs: ManusExecutionOutput[] = (() => {
    if (!activeRoundData || !activeStepId) return [];
    return activeRoundData.round.outputs[activeStepId] || [];
  })();

  const rightPanelActiveStep: ActiveStepInfo | null = (() => {
    if (!activeRoundData || !activeStepId) return null;
    const step = activeRoundData.round.steps.find(s => s.id === activeStepId);
    if (!step) return null;
    return {
      id: step.id,
      type: step.type,
      title: step.title || '',
      subtitle: step.subtitle,
      detail: step.description,
      status: playing ? 'running' : 'completed',
    };
  })();

  // Progress: total steps across all rounds
  const totalSteps = rounds.reduce((acc, r) => acc + r.steps.length, 0);
  const completedSteps =
    rounds.slice(0, state.roundIndex).reduce((acc, r) => acc + r.steps.length, 0) + state.visibleStepCount;
  const progressPercent = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      message.success('Link copied');
    } catch {
      message.error('Copy failed');
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className='flex items-center justify-center h-screen bg-white dark:bg-[#111217]'>
        <div className='text-center space-y-3'>
          <div className='animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto' />
          <p className='text-gray-400'>Loading...</p>
        </div>
      </div>
    );
  }

  if (fetchError || rounds.length === 0) {
    return (
      <div className='flex items-center justify-center h-screen bg-white dark:bg-[#111217]'>
        <div className='text-center space-y-3'>
          <p className='text-2xl font-semibold text-gray-700 dark:text-gray-200'>Share link is invalid or expired</p>
          <p className='text-gray-400'>{fetchError || 'No conversation content to replay'}</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>
          {firstQuestion
            ? `${firstQuestion.slice(0, 60)}${firstQuestion.length > 60 ? '…' : ''} · DB-GPT Replay`
            : 'DB-GPT Conversation Replay'}
        </title>
      </Head>

      <div className='flex flex-col h-screen bg-white dark:bg-[#111217] overflow-hidden'>
        {/* ---------------------------------------------------------------- */}
        {/* Top bar */}
        {/* ---------------------------------------------------------------- */}
        <div className='flex items-center justify-between px-5 py-2.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1a1b1e] flex-shrink-0'>
          <div className='flex items-center gap-3 min-w-0'>
            {/* Logo / brand */}
            <span className='font-bold text-base text-gray-800 dark:text-white flex-shrink-0'>DB-GPT</span>
            <div className='w-px h-4 bg-gray-200 dark:bg-gray-700 flex-shrink-0' />
            <span className='text-xs font-medium text-blue-500 bg-blue-50 dark:bg-blue-500/10 px-2 py-0.5 rounded-full flex-shrink-0'>
              Replay
            </span>
            {firstQuestion && (
              <span className='text-sm text-gray-500 dark:text-gray-400 truncate max-w-[400px]' title={firstQuestion}>
                {firstQuestion}
              </span>
            )}
          </div>

          {/* Playback controls */}
          <div className='flex items-center gap-2'>
            {/* Speed selector */}
            <div className='flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5'>
              {SPEED_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setSpeed(opt.value)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    speed === opt.value
                      ? 'bg-white dark:bg-gray-700 text-gray-800 dark:text-white shadow-sm'
                      : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Divider */}
            <div className='w-px h-5 bg-gray-200 dark:bg-gray-700' />

            {/* Play / Pause */}
            {state.done ? (
              <Button icon={<ReloadOutlined />} onClick={restart}>
                Replay again
              </Button>
            ) : playing ? (
              <Button icon={<PauseCircleOutlined />} onClick={pause}>
                Pause
              </Button>
            ) : (
              <Button type='primary' icon={<PlayCircleOutlined />} onClick={play}>
                {completedSteps === 0 ? 'Start replay' : 'Resume'}
              </Button>
            )}

            {/* Skip to end */}
            {!state.done && (
              <Tooltip title='Jump to last step'>
                <Button icon={<StepForwardOutlined />} onClick={() => jumpToRound(rounds.length - 1)} />
              </Tooltip>
            )}

            {/* Divider */}
            <div className='w-px h-5 bg-gray-200 dark:bg-gray-700' />

            {/* Copy share link — blue to match the UI theme */}
            <Tooltip title='Copy share link; anyone can replay this conversation via the link'>
              <Button
                icon={<LinkOutlined />}
                onClick={handleCopyLink}
                style={{ color: '#3b82f6', borderColor: '#3b82f6' }}
              >
                Share
              </Button>
            </Tooltip>
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Progress bar */}
        {/* ---------------------------------------------------------------- */}
        <div className='px-5 py-2 border-b border-gray-100 dark:border-gray-800/60 bg-gray-50/50 dark:bg-transparent flex-shrink-0'>
          <div className='flex items-center gap-3'>
            <div className='flex-1'>
              <div className='h-1 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden'>
                <div
                  className='h-full bg-blue-500 rounded-full transition-all duration-500 ease-out'
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
            <span className='text-xs text-gray-400 whitespace-nowrap tabular-nums'>
              {completedSteps} / {totalSteps} steps
            </span>
            {/* Round selector tabs */}
            {rounds.length > 1 && (
              <div className='flex items-center gap-1'>
                {rounds.map((round, ri) => (
                  <Tooltip key={ri} title={round.humanText ? round.humanText.slice(0, 40) : `Round ${ri + 1}`}>
                    <button
                      onClick={() => jumpToRound(ri)}
                      className={`w-5 h-5 rounded-full text-[10px] font-bold transition-colors ${
                        ri === state.roundIndex
                          ? 'bg-blue-500 text-white'
                          : ri <= state.completedRoundIndex
                            ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400'
                            : 'bg-gray-200 dark:bg-gray-700 text-gray-400'
                      }`}
                    >
                      {ri + 1}
                    </button>
                  </Tooltip>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Main content: left (steps) + right (output) */}
        {/* ---------------------------------------------------------------- */}
        <div className='flex-1 flex overflow-hidden'>
          {/* Left panel — all rounds stacked */}
          <div className='w-[42%] min-w-[360px] border-r border-gray-200 dark:border-gray-800 flex flex-col overflow-y-auto'>
            {rounds.map((_, ri) => {
              const data = getVisibleRoundData(ri);
              if (!data) return null;

              const isCurrentRound = ri === state.roundIndex;
              const isPastRound = ri < state.roundIndex;
              const isFutureRound = ri > state.roundIndex;

              // Future rounds are hidden until the replay reaches them
              if (isFutureRound) return null;

              const isCollapsed = isPastRound;

              return (
                <ManusLeftPanel
                  key={ri}
                  sections={data.sections}
                  activeStepId={isCurrentRound ? data.activeStepId : undefined}
                  onStepClick={undefined /* read-only */}
                  isWorking={isCurrentRound && playing && !state.showFinalForRound}
                  userQuery={data.round.humanText}
                  assistantText={data.showFinal ? data.round.finalContent : undefined}
                  stepThoughts={data.round.stepThoughts}
                  artifacts={data.showFinal ? data.round.artifacts : []}
                  onViewAllFiles={data.showFinal ? () => setRightPanelView('files') : undefined}
                  isCollapsed={isCollapsed}
                  onExpand={() => jumpToRound(ri)}
                />
              );
            })}

            {/* Pending placeholder for rounds not yet reached */}
            {rounds.length > 1 && state.roundIndex < rounds.length - 1 && (
              <div className='px-4 py-3 text-xs text-gray-400 text-center animate-pulse'>
                {rounds.length - state.roundIndex - 1} round(s) pending replay...
              </div>
            )}
            {/* Bottom breathing room */}
            <div className='flex-shrink-0 h-8' />
          </div>

          {/* Right panel — outputs of the active step */}
          <div className='flex-1 overflow-hidden'>
            <ManusRightPanel
              activeStep={rightPanelActiveStep}
              outputs={rightPanelOutputs}
              isRunning={playing && !!activeStepId}
              artifacts={activeRoundData?.round.artifacts ?? []}
              panelView={rightPanelView}
              onPanelViewChange={setRightPanelView}
            />
          </div>
        </div>
      </div>
    </>
  );
};

export default SharePage;
