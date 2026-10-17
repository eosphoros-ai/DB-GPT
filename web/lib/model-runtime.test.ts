import { describe, expect, it } from 'vitest';
import {
  describeModelConnectionFailure,
  describeModelRequestFailure,
  isModelConnectionFailure,
  resolvePreferredModel,
} from './model-runtime';

describe('model runtime selection', () => {
  it('keeps the explicit current model when the available list is reordered', () => {
    expect(resolvePreferredModel('deepseek-chat', 'deepseek-chat', ['qwen-plus', 'deepseek-chat'])).toBe(
      'deepseek-chat',
    );
  });

  it('restores a persisted model even while it is temporarily absent from the usable list', () => {
    expect(resolvePreferredModel('', 'deepseek-chat', ['qwen-plus'])).toBe('deepseek-chat');
  });

  it('falls back to the first available model only when the user has no selection', () => {
    expect(resolvePreferredModel('', null, ['qwen-plus', 'deepseek-chat'])).toBe('qwen-plus');
  });

  it('identifies and labels a connection failure with the requested model', () => {
    expect(isModelConnectionFailure('LLMServer Generate Error: connection refused')).toBe(true);
    const visibleError = describeModelConnectionFailure('deepseek-chat', 'connection refused', 503);
    expect(visibleError).toBe('模型“deepseek-chat”连接失败（HTTP 503）：connection refused');
    expect(isModelConnectionFailure(visibleError)).toBe(true);
  });

  it('does not mislabel a client-side request error as a connection failure', () => {
    expect(describeModelRequestFailure('deepseek-chat', 'invalid temperature', 422)).toBe(
      '模型“deepseek-chat”请求失败（HTTP 422）：invalid temperature',
    );
  });
});
