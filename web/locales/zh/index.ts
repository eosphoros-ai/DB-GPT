import { ChatZh } from './chat';
import { CommonZh } from './common';
import FinancialZh from './financial';
import { FlowZn } from './flow';
import KsZh from './knowledgeSource';
import { ObservabilityZh } from './observability';
import { SemanticCenterZh } from './semanticCenter';
import { SemanticProvenanceZh } from './semanticProvenance';
import { TaskflowZh } from './taskflow';
import WikiZh from './wiki';

const zh = {
  ...FinancialZh,
  ...ChatZh,
  ...FlowZn,
  ...CommonZh,
  ...ObservabilityZh,
  ...SemanticCenterZh,
  ...SemanticProvenanceZh,
  ...TaskflowZh,
  ...WikiZh,
  ...KsZh,
};

export default zh;
