/** Wrap fixture data in the API success envelope consumed by the frontend. */
const envelope = (data) => ({
  success: true,
  data,
  err_code: null,
  err_msg: null,
});
/** Build a paginated fixture response with consistent item and total counts. */
const paged = (items) => ({
  items,
  total_count: items.length,
  total_pages: 1,
  page: 1,
  page_size: 20,
});
const date = "2026-09-29T10:00:00";
const conversation = {
  conv_uid: "regression-chat",
  user_input: "Regression conversation",
  user_name: "001",
  chat_mode: "chat_normal",
  select_param: "",
  app_code: "",
  gmt_created: date,
  gmt_modified: date,
};
const datasource = {
  id: "regression-sqlite",
  name: "Regression SQLite",
  type: "sqlite",
  db_type: "sqlite",
  db_name: "regression",
  label: "Regression SQLite",
  description: "Isolated browser fixture",
  params: { path: "/test/regression.db", name: "regression" },
};
const params = [
  {
    param_name: "path",
    label: "Database path",
    param_type: "string",
    default_value: "/test/regression.db",
    required: true,
    description: "Fixture database path",
  },
];
const space = {
  id: 1,
  name: "Regression knowledge",
  desc: "Isolated fixture",
  vector_type: "Chroma",
  domain_type: "Normal",
  owner: "001",
  gmt_created: date,
  gmt_modified: date,
};
const flow = {
  uid: "regression-flow",
  dag_id: "regression-flow",
  name: "Regression workflow",
  label: "Regression workflow",
  description: "Fixture flow",
  editable: true,
  state: "developing",
  flow_data: { nodes: [], edges: [] },
  source: "web",
  nick_name: "dbgpt",
  gmt_created: date,
};
const model = {
  model_name: "regression-model",
  worker_type: "llm",
  host: "127.0.0.1",
  port: 5001,
  manager_host: "127.0.0.1",
  manager_port: 5000,
  healthy: true,
  check_healthy: true,
  last_heartbeat: date,
};
const provider = {
  provider: "proxy/openai",
  name: "OpenAI",
  worker_type: "llm",
  proxy: true,
  params: [],
  models: [
    {
      model: "regression-model",
      label: "Regression model",
      enabled: false,
      description: "Test fixture",
      context_length: 8192,
    },
  ],
};
const skill = {
  id: "regression-skill",
  name: "regression-skill",
  description: "Regression skill fixture",
  type: "official",
  skill_type: "data_analysis",
  file_path: "/test/SKILL.md",
};
const task = {
  task_id: "regression-task",
  task_name: "Regression schedule",
  description: "Fixture schedule",
  enabled: true,
  cron_expression: "0 9 * * *",
  timezone: "Asia/Shanghai",
  execution_config: {},
  context_snapshot: {},
  created_at: date,
  updated_at: date,
  next_run_time: date,
};
const history = [
  {
    role: "human",
    context: "Show regression sample",
    order: 1,
    model_name: "regression-model",
    time_stamp: 1790668800,
  },
  {
    role: "view",
    context:
      "## Regression result\n\n```sql\nSELECT 1 AS value;\n```\n\n| Name | Value |\n| --- | --- |\n| Alpha | 10 |\n| Beta | 20 |",
    order: 2,
    model_name: "regression-model",
    time_stamp: 1790668800,
  },
];
/** Resolve a known fixture endpoint; return undefined so the harness records unknown API requests. */
function responseFor(url, method) {
  const p = url.pathname.replace(/\/$/, "");
  if (p === "/api/v1/chat/share/regression-share")
    return {
      messages: [
        { role: "human", context: "Replay this regression answer", order: 0 },
        {
          role: "view",
          order: 1,
          context: JSON.stringify({
            version: 1,
            type: "react-agent",
            steps: [],
            final_content: "Thought: PR3277_SHARE_OK",
          }),
        },
      ],
    };
  if (p === "/api/v1/model/types") return ["regression-model"];
  if (p === "/api/v1/chat/dialogue/list") return [conversation];
  if (p === "/api/v1/chat/dialogue/query_page") return paged([conversation]);
  if (p === "/api/v1/chat/dialogue/messages/history") {
    if (url.searchParams.get("con_uid") === "regression-rich")
      return [
        history[0],
        {
          ...history[1],
          context:
            history[1].context +
            "\n\n```vis-db-chart\n" +
            JSON.stringify({
              data: [
                { category: "Alpha", value: 10 },
                { category: "Beta", value: 20 },
              ],
              describe: "Fixture chart",
              title: "Regression chart",
              type: "bar",
              sql: "SELECT category, value FROM fixture",
            }) +
            "\n```\n\n$E=mc^2$",
        },
      ];
    if (url.searchParams.get("con_uid") === "regression-editor")
      return [
        history[0],
        {
          ...history[1],
          context: JSON.stringify({ template_name: "report", charts: [] }),
        },
      ];
    return history;
  }
  if (p === "/api/v1/chat/dialogue/new")
    return { ...conversation, conv_uid: "regression-created" };
  if (p === "/api/v1/chat/dialogue/scenes") return [];
  if (p === "/api/v1/question/list") return [];
  if (p === "/api/v1/chat/mode/params/list")
    return [{ param: "regression", db_name: "regression" }];
  if (p === "/api/v1/chat/mode/params/info") return {};
  if (
    p === "/api/v1/chat/dialogue/delete" ||
    p === "/api/v1/chat/dialogue/clear"
  )
    return true;
  if (p === "/api/v2/serve/datasources")
    return method === "GET" ? [datasource] : datasource;
  if (p === "/api/v2/serve/datasource-types")
    return {
      types: [
        {
          name: "sqlite",
          label: "SQLite",
          parameters: params,
          description: "SQLite fixture",
        },
      ],
    };
  if (
    p === "/api/v2/serve/datasources/test-connection" ||
    p.endsWith("/refresh")
  )
    return true;
  if (p === "/api/v1/knowledge/space/list") return [space];
  if (p === "/api/v1/knowledge/space/config")
    return { storage: [{ name: "Chroma", desc: "Chroma" }] };
  if (p === "/api/v1/knowledge/document/chunkstrategies")
    return [
      {
        strategy: "Automatic",
        name: "Automatic",
        suffix: ["txt", "md"],
        parameters: [],
      },
    ];
  if (/\/knowledge\/.*\/stats$/.test(p))
    return { graph_vertex_count: 2, graph_edge_count: 1, document_count: 1 };
  if (/\/knowledge\/.*\/document\/list$/.test(p))
    return { data: [], total: 0, page: 1 };
  if (/\/knowledge\/.*\/chunk\/list$/.test(p))
    return { data: [], total: 0, page: 1 };
  if (/\/knowledge\/.*\/arguments$/.test(p))
    return { embedding: {}, prompt: {}, retrieval: {} };
  if (/\/knowledge\/.*\/graphvis$/.test(p))
    return {
      nodes: [
        { id: "a", label: "Alpha" },
        { id: "b", label: "Beta" },
      ],
      edges: [{ id: "ab", source: "a", target: "b", label: "related" }],
    };
  if (p === "/api/v1/skills/list") return [skill];
  if (p === "/api/v1/skills/detail")
    return {
      ...skill,
      raw_content: "# Regression skill\n\nFixture content.",
      file_tree: [],
    };
  if (p === "/api/v1/app/list")
    return { app_list: [], total_count: 0, total_page: 0, current_page: 1 };
  if (p === "/api/v1/app/hot/list") return [];
  if (p === "/api/v1/app/info")
    return {
      app_code: "regression-app",
      app_name: "Regression app",
      app_describe: "Mobile regression",
      team_mode: "single_agent",
      details: [],
    };
  if (p === "/api/v1/team-mode/list")
    return [
      {
        value: "single_agent",
        name_cn: "Single Agent",
        name_en: "Single Agent",
        description: "Single agent test",
      },
      {
        value: "auto_plan",
        name_cn: "Auto Plan",
        name_en: "Auto Plan",
        description: "Auto plan test",
      },
    ];
  if (p === "/api/v1/app/create")
    return {
      app_code: "regression-created-app",
      app_name: "Regression app",
      app_describe: "Browser regression",
      team_mode: "single_agent",
      details: [],
    };
  if (p === "/api/v1/native_scenes") return [];
  if (
    p === "/api/v1/agents/list" ||
    p === "/api/v1/llm-strategy/list" ||
    p === "/api/v1/resource-type/list" ||
    p === "/api/v1/app/resources/list"
  )
    return [];
  if (p === "/api/v2/serve/awel/flows") return paged([flow]);
  if (p === "/api/v2/serve/awel/flows/regression-flow") return flow;
  if (p === "/api/v2/serve/awel/nodes" || p === "/api/v2/serve/awel/variables")
    return [];
  if (
    p === "/api/v2/serve/awel/variables/keys" ||
    p === "/api/v2/serve/awel/flow/templates"
  )
    return [];
  if (p === "/api/v2/serve/model/models") return [model];
  if (p === "/api/v2/serve/model/providers") return [provider];
  if (p === "/api/v2/serve/model/providers/config")
    return { provider: "proxy/openai", connected: false, enabled_models: [] };
  if (p === "/api/v2/serve/model/providers/connect")
    return { provider: "proxy/openai", connected: true, enabled_models: [] };
  if (p === "/api/v2/serve/model/model-types")
    return [
      {
        model: "regression-model",
        provider: "proxy/openai",
        worker_type: "llm",
        params,
        proxy: true,
        enabled: true,
        path_exist: true,
      },
    ];
  if (p === "/api/v1/agent/query")
    return {
      datas: [],
      items: [],
      page_index: 1,
      page_size: 20,
      total_row_count: 0,
      total_page: 0,
    };
  if (p === "/api/v1/agent/my" || p === "/api/v1/dbgpts/list") return [];
  if (
    p === "/api/v1/serve/dbgpts/hub/query_page" ||
    p === "/api/v1/serve/dbgpts/my/query_page"
  )
    return paged([]);
  if (p === "/api/v2/serve/connectors/types") return [];
  if (p === "/api/v2/serve/connectors") return [];
  if (p === "/api/v2/serve/scheduled-tasks") return [task];
  if (p === "/api/v2/serve/scheduled-tasks/regression-task") return task;
  if (p === "/api/v2/serve/scheduled-tasks/regression-task/runs") return [];
  if (p === "/api/v2/serve/scheduled-tasks/regression-task/toggle")
    return { ...task, enabled: false };
  if (
    p === "/api/v1/evaluate/evaluations" ||
    p === "/api/v1/evaluate/datasets" ||
    p === "/api/v1/evaluate/benchmark_task_list"
  )
    return paged([]);
  if (p === "/api/v1/evaluate/test_auth") return true;
  if (p === "/api/v1/evaluate/metrics") return [];
  if (p === "/api/v1/observability/capabilities")
    return ["agents", "traces", "metrics"];
  if (
    p === "/api/v1/observability/agents" ||
    p === "/api/v1/observability/health"
  )
    return [];
  if (
    p === "/api/v1/observability/traces" ||
    p === "/api/v1/observability/sessions" ||
    p === "/api/v1/observability/models/usage"
  )
    return [];
  if (p === "/api/v1/observability/metrics")
    return { metric: url.searchParams.get("metric"), points: [] };
  if (p === "/api/v2/serve/evaluate/benchmark/list_datasets") return [];
  if (p.includes("/observability/") && p.includes("timeseries"))
    return { metric: url.searchParams.get("metric") || "events", points: [] };
  if (p === "/prompt/query_page") return paged([]);
  if (p === "/prompt/type/targets") return [];
  if (p === "/api/v1/feedback/select") return [];
  if (p === "/api/v1/feedback/find") return null;
  if (p === "/api/v1/editor/sql/rounds" || p === "/v1/editor/sql/rounds")
    return [{ db_name: "regression", round: 1, round_name: "Fixture round" }];
  if (p === "/api/v1/editor/sql")
    return [
      {
        sql: "SELECT 1 AS value",
        title: "Regression SQL",
        thoughts: "Fixture query",
        showcase: "bar",
      },
    ];
  if (p === "/api/v1/editor/db/tables")
    return {
      title: "regression",
      key: "regression",
      type: "db",
      children: [
        {
          title: "fixture",
          key: "fixture",
          type: "table",
          children: [
            { title: "value", key: "value", type: "int", children: [] },
          ],
        },
      ],
    };
  if (p === "/api/v1/editor/sql/run")
    return { colunms: ["value"], values: [[1]] };
  if (p === "/api/v1/editor/chart/run")
    return {
      sql_data: { colunms: ["value"], values: [[1]] },
      chart_values: null,
      chart_type: "bar",
    };
  if (p === "/api/v1/chart/editor/submit") return true;
  if (p === "/api/v1/sql/editor/submit") return true;
  if (p === "/api/v1/knowledge/space/add") return [];
  if (/\/knowledge\/.*\/document\/upload$/.test(p)) return 1;
  if (/\/knowledge\/.*\/document\/sync_batch$/.test(p))
    return { success_count: 1, failed_count: 0 };
  if (/\/knowledge\/.*\/tools\/ls-json$/.test(p)) return [];
  if (p === "/api/v1/knowledge/retrieve_strategy_list") return [];
  return undefined;
}
module.exports = {
  envelope,
  responseFor,
  conversation,
  datasource,
  space,
  flow,
  model,
  history,
};
