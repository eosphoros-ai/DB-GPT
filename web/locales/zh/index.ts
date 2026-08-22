import { ChatZh } from './chat';
import { CommonZh } from './common';
import { FlowZn } from './flow';
import { ObservabilityZh } from './observability';

const zh = {
  ...ChatZh,
  ...FlowZn,
  ...CommonZh,
  ...ObservabilityZh,
};

export default zh;
