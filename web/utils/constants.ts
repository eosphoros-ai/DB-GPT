import { ModelType } from '@/types/chat';
import { DBType } from '@/types/db';
import { ModelIconInfo } from '@/types/models';

export const DEFAULT_ICON_URL = '/models/huggingface.svg';

export const MODEL_ICON_MAP: Record<ModelType, { label: string; icon: string }> = new Proxy({} as any, {
  get: (_target, prop) => {
    const modelId = prop as string;
    return {
      label: getModelLabel(modelId),
      icon: getModelIcon(modelId),
    };
  },
});

export const MODEL_ICON_INFO: Record<string, ModelIconInfo> = {
  deepseek: {
    label: 'DeepSeek',
    icon: '/models/deepseek.png',
    patterns: ['deepseek', 'r1'],
  },
  qwen: {
    label: 'Qwen',
    icon: '/models/qwen2.png',
    patterns: ['qwen', 'qwen2', 'qwen2.5', 'qwq', 'qvq'],
  },
  gemini: {
    label: 'Gemini',
    icon: '/models/gemini.png',
    patterns: ['gemini'],
  },
  moonshot: {
    label: 'Moonshot',
    icon: '/models/moonshot.png',
    patterns: ['moonshot'],
  },
  doubao: {
    label: 'Doubao',
    icon: '/models/doubao.png',
    patterns: ['doubao'],
  },
  ernie: {
    label: 'ERNIE',
    icon: '/models/ernie.png',
    patterns: ['ernie'],
  },
  proxyllm: {
    label: 'Proxy LLM',
    icon: '/models/chatgpt.png',
    patterns: ['proxy'],
  },
  chatgpt: {
    label: 'ChatGPT',
    icon: '/models/chatgpt.png',
    patterns: ['chatgpt', 'gpt', 'o1', 'o3'],
  },
  vicuna: {
    label: 'Vicuna',
    icon: '/models/vicuna.jpeg',
    patterns: ['vicuna'],
  },
  chatglm: {
    label: 'ChatGLM',
    icon: '/models/chatglm.png',
    patterns: ['chatglm', 'glm'],
  },
  llama: {
    label: 'Llama',
    icon: '/models/llama.jpg',
    patterns: ['llama', 'llama2', 'llama3'],
  },
  baichuan: {
    label: 'Baichuan',
    icon: '/models/baichuan.png',
    patterns: ['baichuan'],
  },
  claude: {
    label: 'Claude',
    icon: '/models/claude.png',
    patterns: ['claude'],
  },
  bard: {
    label: 'Bard',
    icon: '/models/bard.gif',
    patterns: ['bard'],
  },
  tongyi: {
    label: 'Tongyi',
    icon: '/models/tongyi.apng',
    patterns: ['tongyi'],
  },
  yi: {
    label: 'Yi',
    icon: '/models/yi.svg',
    patterns: ['yi'],
  },
  bailing: {
    label: 'Bailing',
    icon: '/models/bailing.svg',
    patterns: ['bailing'],
  },
  wizardlm: {
    label: 'WizardLM',
    icon: '/models/wizardlm.png',
    patterns: ['wizard'],
  },
  internlm: {
    label: 'InternLM',
    icon: '/models/internlm.png',
    patterns: ['internlm'],
  },
  solar: {
    label: 'Solar',
    icon: '/models/solar_logo.png',
    patterns: ['solar'],
  },
  gorilla: {
    label: 'Gorilla',
    icon: '/models/gorilla.png',
    patterns: ['gorilla'],
  },
  zhipu: {
    label: 'Zhipu',
    icon: '/models/zhipu.png',
    patterns: ['zhipu'],
  },
  falcon: {
    label: 'Falcon',
    icon: '/models/falcon.jpeg',
    patterns: ['falcon'],
  },
  huggingface: {
    label: 'Hugging Face',
    icon: '/models/huggingface.svg',
    patterns: ['huggingface', 'hf'],
  },
};

export function getModelLabel(modelId: string): string {
  if (!modelId) return '';

  // 1. Try to match directly
  if (MODEL_ICON_INFO[modelId]?.label) {
    return MODEL_ICON_INFO[modelId].label;
  }

  // 2. Try to match by patterns to get the base name, then add version information
  const formattedModelId = modelId.toLowerCase();
  for (const key in MODEL_ICON_INFO) {
    const modelInfo = MODEL_ICON_INFO[key];

    if (modelInfo.patterns && modelInfo.patterns.some(pattern => formattedModelId.includes(pattern.toLowerCase()))) {
      // Try to extract version information from the model ID
      const versionMatch = modelId.match(/[-_](\d+b|\d+\.\d+b?|v\d+(\.\d+)?)/i);
      const sizePart = modelId.match(/[-_](\d+b)/i);

      // Build the display name
      let displayName = modelInfo.label;

      // Add version information
      if (versionMatch && !sizePart) {
        displayName += ` ${versionMatch[1]}`;
      }

      // Add size information
      if (sizePart) {
        displayName += ` ${sizePart[1]}`;
      }

      return displayName;
    }
  }

  // If no match
  return modelId;
}

export function getModelIcon(modelId: string): string {
  if (!modelId) return DEFAULT_ICON_URL;

  // Format the model ID for matching
  const formattedModelId = modelId.toLowerCase();

  // 1. Try to match directly
  if (MODEL_ICON_INFO[modelId]?.icon) {
    return MODEL_ICON_INFO[modelId].icon;
  }

  // 2. Try to match by patterns
  for (const key in MODEL_ICON_INFO) {
    const modelInfo = MODEL_ICON_INFO[key];

    // Check if the model ID contains one of the patterns
    if (modelInfo.patterns && modelInfo.patterns.some(pattern => formattedModelId.includes(pattern.toLowerCase()))) {
      return modelInfo.icon;
    }
  }

  // Try to match by the model prefix
  const modelParts = formattedModelId.split(/[-_]/);
  if (modelParts.length > 0) {
    const modelPrefix = modelParts[0];
    for (const key in MODEL_ICON_INFO) {
      if (modelPrefix === key.toLowerCase()) {
        return MODEL_ICON_INFO[key].icon;
      }
    }
  }

  // If no match, return the default icon
  return DEFAULT_ICON_URL;
}

export const dbMapper: Record<DBType, { label: string; icon: string; desc: string }> = {
  mysql: {
    label: 'MySQL',
    icon: '/icons/mysql.png',
    desc: 'Fast, reliable, scalable open-source relational database management system.',
  },
  oceanbase: {
    label: 'OceanBase',
    icon: '/icons/oceanbase.png',
    desc: 'An Ultra-Fast & Cost-Effective Distributed SQL Database.',
  },
  mssql: {
    label: 'MSSQL',
    icon: '/icons/mssql.png',
    desc: 'Powerful, scalable, secure relational database system by Microsoft.',
  },
  duckdb: {
    label: 'DuckDB',
    icon: '/icons/duckdb.png',
    desc: 'In-memory analytical database with efficient query processing.',
  },
  sqlite: {
    label: 'Sqlite',
    icon: '/icons/sqlite.png',
    desc: 'Lightweight embedded relational database with simplicity and portability.',
  },
  clickhouse: {
    label: 'ClickHouse',
    icon: '/icons/clickhouse.png',
    desc: 'Columnar database for high-performance analytics and real-time queries.',
  },
  oracle: {
    label: 'Oracle',
    icon: '/icons/oracle.png',
    desc: 'Robust, scalable, secure relational database widely used in enterprises.',
  },
  access: {
    label: 'Access',
    icon: '/icons/access.png',
    desc: 'Easy-to-use relational database for small-scale applications by Microsoft.',
  },
  mongodb: {
    label: 'MongoDB',
    icon: '/icons/mongodb.png',
    desc: 'Flexible, scalable NoSQL document database for web and mobile apps.',
  },
  doris: {
    label: 'ApacheDoris',
    icon: '/icons/doris.png',
    desc: 'A new-generation open-source real-time data warehouse.',
  },
  starrocks: {
    label: 'StarRocks',
    icon: '/icons/starrocks.png',
    desc: 'An Open-Source, High-Performance Analytical Database.',
  },
  db2: { label: 'DB2', icon: '/icons/db2.png', desc: 'Scalable, secure relational database system developed by IBM.' },
  hbase: {
    label: 'HBase',
    icon: '/icons/hbase.png',
    desc: 'Distributed, scalable NoSQL database for large structured/semi-structured data.',
  },
  redis: {
    label: 'Redis',
    icon: '/icons/redis.png',
    desc: 'Fast, versatile in-memory data structure store as cache, DB, or broker.',
  },
  cassandra: {
    label: 'Cassandra',
    icon: '/icons/cassandra.png',
    desc: 'Scalable, fault-tolerant distributed NoSQL database for large data.',
  },
  couchbase: {
    label: 'Couchbase',
    icon: '/icons/couchbase.png',
    desc: 'High-performance NoSQL document database with distributed architecture.',
  },
  omc: { label: 'Omc', icon: '/icons/odc.png', desc: 'Omc meta data.' },
  postgresql: {
    label: 'PostgreSQL',
    icon: '/icons/postgresql.png',
    desc: 'Powerful open-source relational database with extensibility and SQL standards.',
  },
  vertica: {
    label: 'Vertica',
    icon: '/icons/vertica.png',
    desc: 'Vertica is a strongly consistent, ACID-compliant, SQL data warehouse, built for the scale and complexity of today’s data-driven world.',
  },
  spark: { label: 'Spark', icon: '/icons/spark.png', desc: 'Unified engine for large-scale data analytics.' },
  hive: { label: 'Hive', icon: '/icons/hive.png', desc: 'A distributed fault-tolerant data warehouse system.' },
  space: { label: 'Space', icon: '/icons/knowledge.png', desc: 'knowledge analytics.' },
  tugraph: {
    label: 'TuGraph',
    icon: '/icons/tugraph.png',
    desc: 'TuGraph is a high-performance graph database jointly developed by Ant Group and Tsinghua University.',
  },
};
