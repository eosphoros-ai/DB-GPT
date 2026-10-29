import { ChatEn } from './chat';
import { CommonEn } from './common';
import { FlowEn } from './flow';
import KsEn from './knowledgeSource';
import { ObservabilityEn } from './observability';
import { SemanticCenterEn } from './semanticCenter';
import { SemanticProvenanceEn } from './semanticProvenance';
import { TaskflowEn } from './taskflow';
import WikiEn from './wiki';

const en: Record<string, unknown> = {
  ...ChatEn,
  ...FlowEn,
  ...CommonEn,
  ...ObservabilityEn,
  ...SemanticCenterEn,
  ...SemanticProvenanceEn,
  ...TaskflowEn,
  ...WikiEn,
  ...KsEn,
};

export default en;
