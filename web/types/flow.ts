import { File } from 'buffer';
import { Node } from 'reactflow';

export type FlowState = 'deployed' | 'developing' | 'initializing' | 'testing' | 'disabled' | 'running' | 'load_failed';

export type IFlowUpdateParam = {
  name: string;
  label: string;
  editable: boolean;
  deploy?: boolean;
  description?: string;
  uid?: string;
  flow_data?: IFlowData;
  state?: FlowState;
  variables?: IVariableItem[];
};

export type IFlowRefreshParams = {
  id: string;
  type_name: string;
  type_cls: string;
  flow_type: 'resource' | 'operator';
  refresh: {
    name: string;
    depends?: Array<{
      name: string;
      value: any;
      has_value: boolean;
    }>;
  }[];
};

export type IFlow = {
  dag_id: string;
  gmt_created: string;
  uid: string;
  name: string;
  label: string;
  editable: boolean;
  description: string;
  flow_data: IFlowData;
  source: string;
  gmt_modified?: string;
  admins?: string[];
  nick_name: string;
  state?: FlowState;
  define_type?: string;
  error_message?: string;
};

export interface IFlowResponse {
  items: IFlow[];
  total_count: number;
  total_pages: number;
  page: number;
  page_size: number;
}

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
  ui: IFlowNodeParameterUI;
};

export type IFlowNodeParameterUI = {
  ui_type: string;
  language: string;
  file_types: string;
  action: string;
  attr: {
    disabled: boolean;
    [key: string]: any;
  };
  editor?: {
    width: number;
    height: number;
  };
  show_input?: boolean;
  refresh?: boolean;
  refresh_depends?: string[];
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
  nodes: IFlowDataNode[];
  edges: IFlowDataEdge[];
  variables?: IVariableItem[];
  viewport: IFlowDataViewport;
};

export type IFlowExportParams = {
  uid: string;
  export_type?: 'json' | 'dbgpts';
  format?: 'json' | 'file';
  file_name?: string;
  user_name?: string;
  sys_code?: string;
};

export type IFlowImportParams = {
  file: File;
  save_flow?: boolean;
};

export type IUploadFileRequestParams = {
  files: Array<File>;
  user_name?: string;
  sys_code?: string;
};

export type IUploadFileResponse = {
  file_name: string;
  file_id: string;
  bucket: string;
  uri?: string;
};

export type IGetKeysRequestParams = {
  user_name?: string;
  sys_code?: string;
  category?: string;
};

export type IGetKeysResponseData = {
  key: string;
  label: string;
  description: string;
  value_type: string;
  category: string;
  scope: string;
  scope_key: string | null;
};

export type IGetVariablesByKeyRequestParams = {
  key: string;
  scope: string;
  scope_key?: string;
  user_name?: string;
  sys_code?: string;
  page?: number;
  page_size?: number;
};

export type IGetVariablesByKeyResponseData = {
  items: IVariableItem[];
  total_count: number;
  total_pages: number;
  page: number;
  page_size: number;
};

export type IVariableItem = {
  key: string;
  label: string;
  description: string | null;
  value_type: string;
  category: string;
  scope: string;
  scope_key: string | null;
  name: string;
  value: string;
  enabled: boolean;
  user_name: string | null;
  sys_code: string | null;
  id: number;
  [key: string]: any;
};
