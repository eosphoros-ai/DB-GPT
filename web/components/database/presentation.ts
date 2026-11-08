import { ConfigurableParams } from '@/types/common';
import { DBType, DbListResponse } from '@/types/db';

export type Connection = DbListResponse[0];

export function connectionParams(connection: Connection): Record<string, any> {
  return (connection.params || {}) as unknown as Record<string, any>;
}

export function connectionName(connection: Connection) {
  const params = connectionParams(connection);
  return (
    params.database ||
    params.project ||
    params.path?.split(/[/\\]/).pop() ||
    connection.name ||
    connection.db_name ||
    connection.id
  );
}

export function connectionAddress(connection: Connection) {
  const params = connectionParams(connection);
  return params.path || params.endpoint || [params.host, params.port].filter(Boolean).join(':') || '—';
}

const analytics = new Set([
  'clickhouse',
  'duckdb',
  'spark',
  'hive',
  'maxcompute',
  'apache_doris',
  'doris',
  'starrocks',
  'vertica',
]);
const graphs = new Set(['tugraph', 'neo4j']);
const nosql = new Set(['mongodb', 'redis', 'hbase', 'cassandra', 'couchbase']);

export function databaseCategory(type: DBType) {
  const value = type.toLowerCase();
  if (graphs.has(value)) return 'graph';
  if (nosql.has(value)) return 'nosql';
  if (analytics.has(value)) return 'analytics';
  return 'relational';
}

const basicFields = new Set([
  'host',
  'port',
  'user',
  'username',
  'password',
  'pwd',
  'database',
  'db_name',
  'path',
  'project',
  'access_id',
  'access_key',
  'endpoint',
  'schema',
  'uri',
  'url',
]);

export function isBasicParameter(param: ConfigurableParams) {
  return param.required || basicFields.has(param.param_name);
}

const labels: Record<string, [string, string]> = {
  host: ['主机地址', 'Host'],
  port: ['端口', 'Port'],
  user: ['用户名', 'Username'],
  username: ['用户名', 'Username'],
  password: ['密码', 'Password'],
  pwd: ['密码', 'Password'],
  database: ['数据库名称', 'Database name'],
  db_name: ['数据库名称', 'Database name'],
  path: ['数据库文件路径', 'Database file path'],
  project: ['项目名称', 'Project'],
  access_id: ['访问密钥 ID', 'Access key ID'],
  access_key: ['访问密钥 Secret', 'Access key secret'],
  endpoint: ['服务地址', 'Endpoint'],
  schema: ['Schema', 'Schema'],
  driver: ['连接驱动', 'Driver'],
  check_same_thread: ['启用同线程检查', 'Check same thread'],
};

export function parameterLabel(param: ConfigurableParams, zh: boolean) {
  return labels[param.param_name]?.[zh ? 0 : 1] || param.label || param.param_name;
}

export function useDatabaseCopy(language: string) {
  const zh = language.startsWith('zh');
  const copy = (cn: string, en: string) => (zh ? cn : en);
  return { zh, copy };
}
