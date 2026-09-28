import { ChatZh } from './chat';
import { CommonZh } from './common';
import { FlowZn } from './flow';
import { ObservabilityZh } from './observability';
import WikiZh from './wiki';
import KsZh from './knowledgeSource';

const zh = {
  ...ChatZh,
  ...FlowZn,
  ...CommonZh,
  ...ObservabilityZh,
  ...WikiZh,
  ...KsZh,
};

export default zh;
