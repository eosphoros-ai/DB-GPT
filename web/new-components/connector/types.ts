export type ConnectorStatus = 'active' | 'error' | 'disconnected';

export type AttachedConnector = {
  id: string;
  connector_type: string;
  display_name: string;
};

export interface ConnectorInstance {
  id: string;
  connector_type: string;
  display_name: string;
  status: ConnectorStatus;
  config?: Record<string, unknown>;
  created_at?: string;
}

export interface ConnectorAuthField {
  name: string;
  label: string;
  type: 'text' | 'password' | 'url' | 'select';
  required: boolean;
  options?: string[];
  default?: string;
}

export interface ConnectorCatalogEntry {
  type: string;
  display_name: string;
  description: string;
  icon?: string;
  category: string;
  is_custom?: boolean;
  auth_fields: ConnectorAuthField[];
}

export interface CreateConnectorRequest {
  connector_type: string;
  display_name: string;
  credentials: Record<string, string>;
  config?: Record<string, unknown>;
}

export interface PendingConfirmation {
  confirm_id: string;
  tool_name: string;
  args_summary: string;
  message: string;
  timeout: number;
}

export interface ConfirmActionRequest {
  confirm_id: string;
  approved: boolean;
}
