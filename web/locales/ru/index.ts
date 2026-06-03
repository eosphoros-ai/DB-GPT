import { ChatRu } from './chat';
import { CommonRu } from './common';
import { FlowRu } from './flow';

const ru = {
  ...ChatRu,
  ...FlowRu,
  ...CommonRu,
};

export default ru;
