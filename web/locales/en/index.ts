import { ChatEn } from './chat';
import { CommonEn } from './common';
import { FlowEn } from './flow';
import { ObservabilityEn } from './observability';

const en = {
  ...ChatEn,
  ...FlowEn,
  ...CommonEn,
  ...ObservabilityEn,
};

export default en;
