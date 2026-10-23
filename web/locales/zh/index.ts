import { ChatZh } from './chat';
import { CommonZh } from './common';
import { FlowZn } from './flow';
import KsZh from './knowledgeSource';
import { ObservabilityZh } from './observability';
import { TaskflowZh } from './taskflow';
import WikiZh from './wiki';

const zh = {
  ...ChatZh,
  ...FlowZn,
  ...CommonZh,
  ...ObservabilityZh,
  ...TaskflowZh,
  ...WikiZh,
  ...KsZh,
};

export default zh;
