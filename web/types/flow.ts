import { Node } from 'reactflow';

export type FlowState = 'deployed' | 'developing' | 'initializing' | 'testing' | 'disabled';

export type IFlowUpdateParam = {
  name: string;
  label: string;
  editable: boolean;
  description: string;
  uid?: string;
  flow_data?: IFlowData;
  state?: FlowState;
};

export type IFlow = {
  dag_id: string;
  gmt_created: string;
  gmt_modified: string;
  uid: string;
  name: string;
  label: string;
  editable: boolean;
  description: string;
  flow_data: IFlowData;
  source: string;
  state?: FlowState;
};

export type IFlowResponse = {
  items: Array<IFlow>;
  total_count: number;
  total_pages: number;
  page: number;
  page_size: number;
};

export type IFlowNodeParameter = {
  id: string;
  type_name: string;
  type_cls: string;
  label: string;
  name: string;
  category: string;
  optional: boolean;
  default?: any;
  placeholder?: any;
  description: string;
  options?: any;
  value: any;
  is_list?: boolean;
};

export type IFlowNodeInput = {
  type_name: string;
  type_cls: string;
  label: string;
  name: string;
  description: string;
  id: string;
  optional?: boolean | undefined;
  value: any;
  is_list?: boolean;
};

export type IFlowNodeOutput = {
  type_name: string;
  type_cls: string;
  label: string;
  name: string;
  description: string;
  id: string;
  optional?: boolean | undefined;
  is_list?: boolean;
};

export type IFlowNode = Node & {
  type_name: string;
  type_cls: string;
  parent_cls?: string; // resource have this key
  label: string;
  name: string;
  description: string;
  category: string;
  category_label: string;
  flow_type: 'resource' | 'operator';
  icon?: string;
  documentation_url?: null;
  id: string;
  tags?: any;
  parameters: Array<IFlowNodeParameter>;
  inputs: Array<IFlowNodeInput>;
  outputs: Array<IFlowNodeOutput>;
  version: string;
  invalid?: boolean;
};

interface Position {
  x: number;
  y: number;
  zoom: number;
}

// flodata, the data of the flow
export type IFlowDataNode = {
  width: number;
  height: number;
  id: string;
  position: Position;
  position_absolute?: Position;
  positionAbsolute?: Position;
  data: IFlowNode;
  type: string;
};

export type IFlowDataEdge = {
  source: string;
  target: string;
  source_handle?: string;
  sourceHandle?: string;
  target_handle?: string;
  targetHandle?: string;
  id: string;
  type: string;
};

export type IFlowDataViewport = {
  x: number;
  y: number;
  zoom: number;
};

export type IFlowData = {
  nodes: Array<IFlowDataNode>;
  edges: Array<IFlowDataEdge>;
  viewport: IFlowDataViewport;
};
