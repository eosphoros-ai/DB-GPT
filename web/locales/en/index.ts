import { ChatEn } from './chat';
import { CommonEn } from './common';
import { FlowEn } from './flow';
import { ObservabilityEn } from './observability';
import WikiEn from './wiki';
import KsEn from './knowledgeSource';

const en: Record<string, unknown> = {
  ...ChatEn,
  ...FlowEn,
  ...CommonEn,
  ...ObservabilityEn,
  ...WikiEn,
  ...KsEn,
};

export default en;
