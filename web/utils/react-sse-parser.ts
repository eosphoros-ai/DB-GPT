/**
 * ReAct Agent SSE Event Parser
 *
 * Parses SSE events from the DB-GPT ReAct Agent API and converts them
 * to the OpenCode MessagePart format for rendering.
 *
 * SSE Event Types from Backend:
 * - step.start: New ReAct step started { type, step, id, title, detail }
 * - step.chunk: Streaming chunk { type, id, output_type, content }
 * - step.meta: Step metadata { type, id, thought, action, action_input }
 * - step.done: Step completed { type, id, status }
 * - context.status: Context budget status { type, used, budget, ratio, state, compact_layer }
 * - final: Final answer { type, content }
 * - done: Stream completed { type }
 */

import { MessagePart, ReasoningPart, ToolPart, ToolStatus } from '@/new-components/chat/content/OpenCodeSessionTurn';

// SSE Event Types
export interface SSEStepStartEvent {
  type: 'step.start';
  step: number;
  id: string;
  title: string;
  detail: string;
}

export interface SSEStepChunkEvent {
  type: 'step.chunk';
  id: string;
  output_type: 'thought' | 'text' | 'chart' | string;
  content: any;
}

export interface SSEStepMetaEvent {
  type: 'step.meta';
  id: string;
  thought?: string;
  action?: string;
  action_input?: any;
}

export interface SSEStepDoneEvent {
  type: 'step.done';
  id: string;
  status: 'done' | 'failed';
}

export interface SSEFinalEvent {
  type: 'final';
  content: string;
}

export interface SSEDoneEvent {
  type: 'done';
}

export interface SSEContextStatusEvent {
  type: 'context.status';
  used: number;
  budget: number;
  ratio: number;
  /** Backend sends lowercase ("normal","warning","error","critical","overflow");
   *  mapped to display states in handleContextStatus. */
  state: string;
  compact_layer?: string | null;
}

// ── Human-in-the-loop: question events ──────────────────────────────────────

export interface QuestionOption {
  label: string;
  description: string;
}

export interface QuestionInfo {
  question: string;
  header: string;
  options: QuestionOption[];
  multiple?: boolean;
  custom?: boolean;
}

export interface SSEQuestionAskedEvent {
  type: 'question.asked';
  request_id: string;
  conv_id: string;
  questions: QuestionInfo[];
}

export interface SSEQuestionRepliedEvent {
  type: 'question.replied';
  request_id: string;
}

export interface SSEQuestionRejectedEvent {
  type: 'question.rejected';
  request_id: string;
}

export type SSEEvent =
  | SSEStepStartEvent
  | SSEStepChunkEvent
  | SSEStepMetaEvent
  | SSEStepDoneEvent
  | SSEContextStatusEvent
  | SSEQuestionAskedEvent
  | SSEQuestionRepliedEvent
  | SSEQuestionRejectedEvent
  | SSEFinalEvent
  | SSEDoneEvent;

// Internal state for tracking context budget
export interface ContextStatus {
  used: number;
  budget: number;
  ratio: number;
  state: 'OK' | 'WARNING' | 'ERROR';
  compactLayer?: string | null;
}

// Internal state for tracking steps
interface StepState {
  id: string;
  tool: string;
  status: ToolStatus;
  thought?: string;
  action?: string;
  actionInput?: any;
  output: string[];
  error?: string;
}

/**
 * ReAct SSE Parser State
 * Manages the state of the ReAct streaming session
 */
export class ReActSSEState {
  private steps: Map<string, StepState> = new Map();
  private stepOrder: string[] = [];
  private finalContent: string = '';
  private isDone: boolean = false;
  private startTime: number;
  private endTime?: number;
  private _contextStatus: ContextStatus | null = null;
  private _pendingQuestion: SSEQuestionAskedEvent | null = null;

  constructor() {
    this.startTime = Date.now();
  }

  /**
   * Process an SSE event and update internal state
   */
  processEvent(event: SSEEvent): void {
    switch (event.type) {
      case 'step.start':
        this.handleStepStart(event);
        break;
      case 'step.chunk':
        this.handleStepChunk(event);
        break;
      case 'step.meta':
        this.handleStepMeta(event);
        break;
      case 'step.done':
        this.handleStepDone(event);
        break;
      case 'context.status':
        this.handleContextStatus(event);
        break;
      case 'question.asked':
        this._pendingQuestion = event;
        break;
      case 'question.replied':
      case 'question.rejected':
        this._pendingQuestion = null;
        break;
      case 'final':
        this.handleFinal(event);
        break;
      case 'done':
        this.handleDone();
        break;
    }
  }

  /**
   * Get the current pending question (null if none)
   */
  getPendingQuestion(): SSEQuestionAskedEvent | null {
    return this._pendingQuestion;
  }

  private handleStepStart(event: SSEStepStartEvent): void {
    const step: StepState = {
      id: event.id,
      tool: this.mapTitleToTool(event.title),
      status: 'running',
      output: [],
    };
    this.steps.set(event.id, step);
    this.stepOrder.push(event.id);
  }

  private handleStepChunk(event: SSEStepChunkEvent): void {
    const step = this.steps.get(event.id);
    if (!step) return;

    if (event.output_type === 'thought') {
      // Accumulate thought content
      step.thought = (step.thought || '') + event.content;
    } else {
      // Accumulate output content
      const content = typeof event.content === 'string' ? event.content : JSON.stringify(event.content, null, 2);
      step.output.push(content);
    }
  }

  private handleStepMeta(event: SSEStepMetaEvent): void {
    const step = this.steps.get(event.id);
    if (!step) return;

    if (event.thought) step.thought = event.thought;
    if (event.action) {
      step.action = event.action;
      step.tool = this.mapActionToTool(event.action);
    }
    if (event.action_input !== undefined) {
      step.actionInput = event.action_input;
    }
  }

  private handleStepDone(event: SSEStepDoneEvent): void {
    const step = this.steps.get(event.id);
    if (!step) return;

    step.status = event.status === 'done' ? 'completed' : 'error';
    if (event.status === 'failed') {
      step.error = 'Step execution failed';
    }
  }

  private handleFinal(event: SSEFinalEvent): void {
    this.finalContent = event.content;
  }

  private handleDone(): void {
    this.isDone = true;
    this.endTime = Date.now();
  }

  private handleContextStatus(event: SSEContextStatusEvent): void {
    if (!Number.isFinite(event.budget) || event.budget <= 0) {
      this._contextStatus = null;
      return;
    }
    // Map backend state values (lowercase: "normal", "warning", "error",
    // "critical", "overflow") to frontend display states ("OK", "WARNING", "ERROR").
    const stateMap: Record<string, 'OK' | 'WARNING' | 'ERROR'> = {
      normal: 'OK',
      warning: 'WARNING',
      error: 'ERROR',
      critical: 'ERROR',
      overflow: 'ERROR',
      // Also accept the frontend format directly (idempotent)
      OK: 'OK',
      WARNING: 'WARNING',
      ERROR: 'ERROR',
    };
    const mappedState = stateMap[event.state] || 'OK';

    this._contextStatus = {
      used: event.used,
      budget: event.budget,
      ratio: event.ratio,
      state: mappedState,
      compactLayer: event.compact_layer,
    };
  }

  /**
   * Get latest context budget status (null if none received yet)
   */
  getContextStatus(): ContextStatus | null {
    return this._contextStatus;
  }

  /**
   * Map ReAct step title to OpenCode tool name
   */
  private mapTitleToTool(title: string): string {
    const lowerTitle = title.toLowerCase();

    // Map common tool names
    if (lowerTitle.includes('load_skill')) return 'skill';
    if (lowerTitle.includes('select_skill')) return 'question';
    if (lowerTitle.includes('load_file')) return 'read';
    if (lowerTitle.includes('execute_analysis')) return 'bash';
    if (lowerTitle.includes('load_tools')) return 'list';
    if (lowerTitle.includes('execute_tool')) return 'bash';
    if (lowerTitle.includes('terminate')) return 'task';
    if (lowerTitle.includes('react round')) return 'task';

    return 'task'; // Default tool
  }

  /**
   * Map ReAct action name to OpenCode tool name
   */
  private mapActionToTool(action: string): string {
    const lowerAction = action.toLowerCase();

    // Map common actions to OpenCode tool types
    const actionMap: Record<string, string> = {
      load_skills: 'list',
      select_skill: 'question',
      load_skill: 'skill',
      load_file: 'read',
      execute_analysis: 'bash',
      load_tools: 'list',
      execute_tool: 'bash',
      terminate: 'task',
      // Add more mappings as needed
      read: 'read',
      write: 'write',
      edit: 'edit',
      search: 'grep',
      grep: 'grep',
      glob: 'glob',
      bash: 'bash',
      webfetch: 'webfetch',
    };

    return actionMap[lowerAction] || 'task';
  }

  /**
   * Convert current state to OpenCode MessagePart array
   */
  toMessageParts(): MessagePart[] {
    const parts: MessagePart[] = [];

    for (const stepId of this.stepOrder) {
      const step = this.steps.get(stepId);
      if (!step) continue;

      // Skip terminate action — its output is shown as finalContent, not as a step card
      if (step.action && step.action.toLowerCase() === 'terminate') {
        // If terminate has output and we don't yet have finalContent, use it
        if (!this.finalContent && step.output.length > 0) {
          this.finalContent = step.output.join('\n');
        }
        continue;
      }

      // Add thinking/reasoning part if available
      if (step.thought) {
        parts.push({
          id: `${stepId}-reasoning`,
          type: 'reasoning',
          text: step.thought,
        } as ReasoningPart);
      }

      // Add tool part
      const toolPart: ToolPart = {
        id: stepId,
        type: 'tool',
        tool: step.tool,
        state: {
          status: step.status,
          input: step.actionInput
            ? typeof step.actionInput === 'object'
              ? step.actionInput
              : { value: step.actionInput }
            : undefined,
          output: step.output.length > 0 ? step.output.join('\n') : undefined,
          error: step.error,
          metadata: step.action ? { action: step.action } : undefined,
        },
      };
      parts.push(toolPart);
    }

    return parts;
  }

  /**
   * Get final assistant message
   */
  getFinalContent(): string {
    return this.finalContent;
  }

  /**
   * Check if stream is complete
   */
  isComplete(): boolean {
    return this.isDone;
  }

  /**
   * Check if still working (has running steps or not done)
   */
  isWorking(): boolean {
    if (this.isDone) return false;

    for (const step of this.steps.values()) {
      if (step.status === 'running' || step.status === 'pending') {
        return true;
      }
    }

    return !this.isDone;
  }

  /**
   * Get start time
   */
  getStartTime(): number {
    return this.startTime;
  }

  /**
   * Get end time (if complete)
   */
  getEndTime(): number | undefined {
    return this.endTime;
  }

  /**
   * Get current status text for display
   */
  getCurrentStatus(): string {
    // Find the last running step
    for (let i = this.stepOrder.length - 1; i >= 0; i--) {
      const step = this.steps.get(this.stepOrder[i]);
      if (step && step.status === 'running') {
        if (step.action) {
          return `Executing ${step.action}...`;
        }
        return 'Processing...';
      }
    }

    if (this.isDone) return 'Completed';
    return 'Thinking...';
  }
}

/**
 * Parse a single SSE data line
 */
export function parseSSELine(line: string): SSEEvent | null {
  // Remove 'data: ' prefix
  const dataPrefix = 'data: ';
  if (!line.startsWith(dataPrefix)) {
    return null;
  }

  const jsonStr = line.slice(dataPrefix.length).trim();
  if (!jsonStr) {
    return null;
  }

  try {
    return JSON.parse(jsonStr) as SSEEvent;
  } catch (e) {
    console.error('Failed to parse SSE event:', jsonStr, e);
    return null;
  }
}

/**
 * Parse multiple SSE lines (split by \n\n)
 */
export function parseSSEChunk(chunk: string): SSEEvent[] {
  const events: SSEEvent[] = [];
  const lines = chunk.split('\n');

  for (const line of lines) {
    const trimmedLine = line.trim();
    if (trimmedLine.startsWith('data:')) {
      const event = parseSSELine(trimmedLine);
      if (event) {
        events.push(event);
      }
    }
  }

  return events;
}

/**
 * Create a new ReAct SSE state instance
 */
export function createReActSSEState(): ReActSSEState {
  return new ReActSSEState();
}
