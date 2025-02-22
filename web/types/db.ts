import { ConfigurableParams } from '@/types/common';

export type DBOption = {
  label: string;
  value: DBType;
  disabled?: boolean;
  isFileDb?: boolean;
  icon: string;
  desc?: string;
  parameters?: ConfigurableParams[];
};

export type DBType =
  | 'mysql'
  | 'duckdb'
  | 'sqlite'
  | 'mssql'
  | 'clickhouse'
  | 'oracle'
  | 'postgresql'
  | 'vertica'
  | 'db2'
  | 'access'
  | 'mongodb'
  | 'starrocks'
  | 'hbase'
  | 'redis'
  | 'cassandra'
  | 'couchbase'
  | (string & {});

export type IChatDbSchema = {
  type: string;
  id: string;
  name: string;
  label: string;
  description: string;
  params: any[];
  parameters: any[];
  comment: string;
  db_host: string;
  db_name: string;
  db_path: string;
  db_port: number;
  db_pwd: string;
  db_type: DBType;
  db_user: string;
};

export type DbListResponse = IChatDbSchema[];
export type IChatDbSupportTypeSchema = {
  db_type: DBType;
  name: string;
  params: ConfigurableParams;
  types: any[];
  label: string;
  description: string;
  parameters: any[];
};

export type DbSupportTypeResponse = IChatDbSupportTypeSchema[];

export type PostDbParams = Partial<DbListResponse[0] & { file_path: string }>;

export type ChatFeedBackSchema = {
  conv_uid: string;
  conv_index: number;
  question: string;
  knowledge_space: string;
  score: number;
  ques_type: string;
  messages: string;
};

export type PostDbRefreshParams = {
  id: number | string;
};
