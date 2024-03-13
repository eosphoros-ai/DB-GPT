export type DBOption = { label: string; value: DBType; disabled?: boolean; isFileDb?: boolean; icon: string; desc?: string };

export type DBType =
  | 'mysql'
  | 'duckdb'
  | 'sqlite'
  | 'mssql'
  | 'clickhouse'
  | 'oracle'
  | 'postgresql'
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
  is_file_db: boolean;
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

export type PromptProps = {
  id: number;
  chat_scene: string;
  sub_chat_scene: string;
  prompt_type: string;
  content: string;
  user_name: string;
  prompt_name: string;
  gmt_created: string;
  gmt_modified: string;
};
