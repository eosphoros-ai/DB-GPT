export type ConnectorStatus = 'active' | 'error' | 'disconnected' | 'needs_reactivation';

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
  is_custom?: boolean;
}

export interface ConnectorToolArgSummary {
  type: string;
  required: boolean;
  description: string;
}

export interface ConnectorToolArgTruncated {
  _truncated: true;
  byte_count: number;
}

export interface ConnectorToolSummary {
  /** Full routing name (e.g. ``mcp__arxiv-search__search_papers``) — what LLMs invoke. */
  name: string;
  /** Tool name as declared by the MCP server itself (no prefix) — what users see. */
  original_name?: string;
  description: string;
  args: Record<string, ConnectorToolArgSummary | ConnectorToolArgTruncated>;
}

export interface ConnectorToolsResponse {
  connector_id: string;
  state: 'active' | 'inactive' | 'not_mcp';
  tools: ConnectorToolSummary[];
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
