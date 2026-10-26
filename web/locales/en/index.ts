import { ChatEn } from './chat';
import { CommonEn } from './common';
import FinancialEn from './financial';
import { FlowEn } from './flow';
import KsEn from './knowledgeSource';
import { ObservabilityEn } from './observability';
import WikiEn from './wiki';

const en: Record<string, unknown> = {
  ...FinancialEn,
  ...ChatEn,
  ...FlowEn,
  ...CommonEn,
  ...ObservabilityEn,
  ...WikiEn,
  ...KsEn,
};

export default en;
