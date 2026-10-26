import { ChatZh } from './chat';
import { CommonZh } from './common';
import FinancialZh from './financial';
import { FlowZn } from './flow';
import KsZh from './knowledgeSource';
import { ObservabilityZh } from './observability';
import WikiZh from './wiki';

const zh = {
  ...FinancialZh,
  ...ChatZh,
  ...FlowZn,
  ...CommonZh,
  ...ObservabilityZh,
  ...WikiZh,
  ...KsZh,
};

export default zh;
