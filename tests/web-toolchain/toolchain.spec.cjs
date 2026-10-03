const fs = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");
const { envelope, responseFor } = require("./fixtures.cjs");
const mode = process.env.REGRESSION_MODE || "production";
const records = path.join(
  process.env.REGRESSION_OUTPUT || path.join(__dirname, "results"),
  mode,
  "records",
);
fs.mkdirSync(records, { recursive: true });
const routes = [
  ["home", "/"],
  ["conversations", "/conversations/"],
  ["data-sources", "/construct/database/"],
  ["knowledge", "/construct/knowledge/"],
  ["applications", "/construct/app/"],
  ["workflows", "/construct/flow/"],
  ["workflow-canvas", "/construct/flow/canvas/?id=regression-flow"],
  ["models", "/construct/models/"],
  ["model-providers", "/construct/models-config/"],
  ["agent-plugins", "/construct/agent/"],
  ["dbgpts", "/construct/dbgpts/"],
  ["prompts", "/construct/prompt/"],
  ["prompt-editor", "/construct/prompt/add/"],
  ["connectors", "/construct/connectors/"],
  ["skills", "/construct/skills/"],
  ["scheduled-tasks", "/construct/scheduled-tasks/"],
  ["scheduled-task-runs", "/construct/scheduled-tasks/regression-task/"],
  ["evaluation", "/evaluation/"],
  ["model-evaluation", "/models_evaluation/"],
  ["model-datasets", "/models_evaluation/datasets/"],
  ["observability", "/observability/"],
  ["traces", "/observability/traces/"],
  ["data-index", "/data_index/"],
  ["chat", "/chat/?scene=chat_normal&id=regression-chat"],
  [
    "mobile-chat",
    "/mobile/chat/?chat_scene=chat_normal&app_code=regression-app",
  ],
  ["rich-chat", "/chat/?scene=chat_normal&id=regression-rich"],
  [
    "legacy-chart-chat",
    "/chat/?scene=chat_dashboard&id=regression-editor&db_name=regression",
  ],
  ["knowledge-graph", "/knowledge/graph/?spaceName=Regression%20knowledge"],
  [
    "knowledge-detail",
    "/construct/knowledge/detail/?spaceName=Regression%20knowledge",
  ],
];
/** Install deterministic API fixtures and collect console, page and network diagnostics for one page. */
async function instrument(page) {
  const record = {
    mode,
    url: "",
    requests: [],
    unknownApis: [],
    pageErrors: [],
    console: [],
    failedRequests: [],
    badResponses: [],
    steps: [],
    startedAt: new Date().toISOString(),
  };
  page.on("pageerror", (error) =>
    record.pageErrors.push({ message: error.message, stack: error.stack }),
  );
  page.on("console", (msg) => {
    if (["warning", "error"].includes(msg.type()))
      record.console.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location(),
      });
  });
  page.on("requestfailed", (request) =>
    record.failedRequests.push({
      url: request.url(),
      error: request.failure()?.errorText,
      type: request.resourceType(),
    }),
  );
  page.on("response", (response) => {
    if (response.status() >= 400)
      record.badResponses.push({
        url: response.url(),
        status: response.status(),
      });
  });
  await page.context().route(
    (url) =>
      url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/v1/") ||
      url.pathname.startsWith("/prompt/") ||
      (url.port === "5670" && url.pathname.startsWith("/knowledge/")),
    async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      record.requests.push({
        method: req.method(),
        path: url.pathname,
        query: url.search,
        body: req.postData(),
      });
      let data = responseFor(url, req.method());
      if (data === undefined) {
        record.unknownApis.push({ method: req.method(), path: url.pathname });
        data = [];
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(envelope(data)),
      });
    },
  );
  return record;
}
/** Persist the case diagnostics and a best-effort page screenshot, including when assertions fail. */
async function finish(page, record, id) {
  record.url = page.url();
  record.snapshot = await page
    .locator("body")
    .ariaSnapshot()
    .catch((error) => String(error));
  record.finishedAt = new Date().toISOString();
  fs.writeFileSync(
    path.join(records, id + ".json"),
    JSON.stringify(record, null, 2),
  );
  await page
    .screenshot({
      path: path.join(records, id + ".png"),
      fullPage: true,
      timeout: 20000,
    })
    .catch(() => {});
}
/** Reject browser, HTTP and fixture errors; permit only requests cancelled by navigation. */
async function checkHealth(page, record) {
  await expect(page.locator("body")).not.toContainText(
    /Application error:|Unhandled Runtime Error|Internal Server Error/,
  );
  expect(record.pageErrors, "Uncaught browser errors").toEqual([]);
  expect(record.unknownApis, "Fixture coverage gaps").toEqual([]);
  expect(record.badResponses, "HTTP errors").toEqual([]);
  expect(
    record.failedRequests.filter((r) => !r.error?.includes("ERR_ABORTED")),
    "Network failures",
  ).toEqual([]);
  expect(record.console, "Browser console warnings/errors").toEqual([]);
}
for (const [id, route] of routes) {
  test("route: " + id, async ({ page }) => {
    const record = await instrument(page);
    try {
      const response = await page.goto(route, {
        waitUntil: "domcontentloaded",
      });
      expect(response.status()).toBe(200);
      await page
        .waitForLoadState("networkidle", { timeout: 30000 })
        .catch(() => {});
      await expect(page.locator("body")).not.toContainText(
        /Application error:|Unhandled Runtime Error|Internal Server Error/,
      );
      await expect
        .poll(
          async () => (await page.locator("body").innerText()).trim().length,
        )
        .toBeGreaterThan(20);
      await checkHealth(page, record);
    } finally {
      await finish(page, record, id);
    }
  });
}
module.exports = { instrument, finish };

/** Register an interaction case with shared instrumentation, health assertions and evidence capture. */
function interaction(id, route, action) {
  test("interaction: " + id, async ({ page, context }) => {
    const record = await instrument(page);
    try {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await action(page, record, context);
      await page
        .waitForLoadState("networkidle", { timeout: 30000 })
        .catch(() => {});
      await checkHealth(page, record);
    } finally {
      await finish(page, record, "interaction-" + id);
    }
  });
}
/** Wait until the frontend sends a request matching the required endpoint and optional method. */
const waitRequest = (record, fragment, method) =>
  expect
    .poll(() =>
      record.requests.some(
        (r) => r.path.includes(fragment) && (!method || r.method === method),
      ),
    )
    .toBe(true);
interaction("navigation-and-search", "/", async (page) => {
  await expect(page.getByRole("heading", { level: 1 })).toContainText("DB-GPT");
  await page.getByRole("link", { name: "datasources_icon 数据源" }).click();
  await expect(page).toHaveURL(/construct\/database/);
  await page.getByRole("tab", { name: "partition 知识库" }).click();
  await expect(
    page.getByText("Regression knowledge", { exact: true }),
  ).toBeVisible();
  await page.getByPlaceholder("请输入关键词").fill("Regression");
  await page.getByRole("link", { name: "explore_icon 探索广场" }).click();
  await expect(page.getByRole("textbox").first()).toBeVisible();
});
interaction(
  "database-form-and-submit",
  "/construct/database/",
  async (page, r) => {
    await page.getByRole("button", { name: "plus 添加数据源" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "提 交" }).click();
    await expect(
      dialog.getByText("请选择数据库类型", { exact: true }),
    ).toBeVisible();
    await dialog.getByRole("combobox").click();
    await page
      .locator(".ant-select-item-option-content")
      .getByText("Sqlite", { exact: true })
      .click();
    await dialog
      .getByLabel("Database path", { exact: false })
      .fill("/test/regression-created.db");
    await dialog.getByPlaceholder("请输入描述").fill("Browser regression");
    await dialog.getByRole("button", { name: "提 交" }).click();
    await waitRequest(r, "datasources/test-connection", "POST");
    await expect
      .poll(
        () =>
          r.requests.filter(
            (x) =>
              x.path === "/api/v2/serve/datasources" && x.method === "POST",
          ).length,
      )
      .toBe(1);
    await expect(dialog).not.toBeVisible();
  },
);
interaction("knowledge-upload", "/construct/knowledge/", async (page, r) => {
  await page.getByRole("button", { name: "plus 创建知识库" }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "* 知识库名称", exact: true })
    .fill("regression-doc");
  await dialog.getByPlaceholder("请输入描述").fill("Browser regression");
  await dialog.locator("#create_knowledge input[type=file]").setInputFiles({
    name: "regression.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Regression\n\nKnowledge upload test."),
  });
  await expect(
    dialog.getByText("regression.md", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "collapsed 高级设置" }).click();
  await dialog.getByRole("button", { name: "创建并上传" }).click();
  await waitRequest(r, "/document/upload", "POST");
  await waitRequest(r, "/document/sync_batch", "POST");
  await expect(dialog).not.toBeVisible();
});
interaction("application-create", "/construct/app/", async (page, r) => {
  await page.getByRole("button", { name: "plus 创建应用" }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .locator("form")
    .getByText("Single Agent", { exact: true })
    .click();
  await dialog.getByPlaceholder("请输入应用名称").fill("Regression app");
  await dialog.getByPlaceholder("请输入描述").fill("Browser regression");
  await dialog.getByRole("button", { name: "确 定" }).click();
  await waitRequest(r, "/app/create", "POST");
  await expect(page).toHaveURL(/construct\/app\/extra/);
  await expect(page.locator("body")).toContainText("Regression app");
});
interaction(
  "provider-connection-form",
  "/construct/models-config/",
  async (page, r) => {
    await page.getByRole("button", { name: "连 接" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "连 接" }).click();
    await expect(dialog.locator(".ant-form-item-explain-error")).toBeVisible();
    await dialog
      .getByPlaceholder("sk-...")
      .fill("regression-placeholder-not-a-secret");
    await dialog.getByRole("button", { name: "连 接" }).click();
    await waitRequest(r, "/providers/connect", "POST");
    await expect(dialog).not.toBeVisible();
  },
);
interaction(
  "schedule-search-edit-and-toggle",
  "/construct/scheduled-tasks/",
  async (page, r) => {
    await expect(
      page.getByText("Regression schedule", { exact: true }),
    ).toBeVisible();
    await page
      .getByPlaceholder("搜索任务名称、描述...")
      .fill("no-matching-task");
    await expect(
      page.getByText("Regression schedule", { exact: true }),
    ).not.toBeVisible();
    await page.getByPlaceholder("搜索任务名称、描述...").fill("Regression");
    await page.getByRole("switch").click();
    await waitRequest(r, "/regression-task/toggle", "POST");
    await page.getByRole("button", { name: "edit", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByPlaceholder("请输入定时任务名称")
      .fill("Updated regression schedule");
    await dialog
      .getByPlaceholder("定时执行时回放的原始问题")
      .fill("Only reply with OK");
    await dialog.getByRole("radio", { name: "每周", exact: true }).check();
    await dialog.getByRole("button", { name: "保 存" }).click();
    await waitRequest(r, "/regression-task", "PUT");
    await expect(dialog).not.toBeVisible();
  },
);
interaction(
  "skill-search-toggle-and-markdown",
  "/construct/skills/",
  async (page) => {
    const search = page.getByPlaceholder("搜索技能");
    await search.fill("no-matching-skill");
    await expect(
      page.getByText("regression-skill", { exact: true }),
    ).not.toBeVisible();
    await search.fill("regression");
    await page.getByRole("switch").last().click();
    await expect(page.getByRole("switch").last()).not.toBeChecked();
    await page.getByText("regression-skill", { exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Regression skill" }),
    ).toBeVisible();
  },
);
interaction(
  "markdown-chart-sql-data-and-download",
  "/chat/?scene=chat_normal&id=regression-rich",
  async (page, r, context) => {
    await expect(
      page.locator("code").filter({ hasText: "SELECT 1" }),
    ).toBeVisible();
    await expect(page.locator("canvas").first()).toBeVisible();
    await expect(page.locator(".katex").first()).toBeVisible();
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page
      .getByRole("button", { name: "copy", exact: true })
      .nth(1)
      .click();
    await expect
      .poll(() => page.evaluate(() => navigator.clipboard.readText()))
      .toContain("SELECT 1");
    await page.getByRole("tab", { name: "SQL", exact: true }).click();
    await expect(page.getByRole("tabpanel", { name: "SQL" })).toContainText(
      "SELECT category, value FROM fixture",
    );
    await page.getByRole("tab", { name: "Data", exact: true }).click();
    await expect(page.getByRole("tabpanel", { name: "Data" })).toContainText(
      "Alpha",
    );
    await page.getByRole("tab", { name: "Chart", exact: true }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "download", exact: true }).click();
    const file = await download;
    expect(await file.failure()).toBeNull();
    await file.saveAs(path.join(records, "chart-download.png"));
  },
);
interaction(
  "monaco-sql-run-and-save",
  "/chat/?scene=chat_dashboard&id=regression-editor&db_name=regression",
  async (page, r) => {
    await page.getByText("Editor", { exact: true }).click();
    const editor = page.locator(".monaco-editor").first();
    await expect(editor).toBeVisible();
    const input = editor.getByRole("textbox", { name: /Editor content/ });
    // Windows WebKit reports Win32 but uses its macOS user-agent key bindings.
    const selectAll = await page.evaluate(() =>
      /Mac/.test(navigator.userAgent) ? "Meta+A" : "Control+A",
    );
    await input.focus();
    await page.keyboard.press(selectAll);
    await page.keyboard.type("SEL", { delay: 20 });
    await page.keyboard.press("Control+Space");
    await expect(
      editor.getByRole("option", { name: "SELECT", exact: true }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await page.keyboard.press(selectAll);
    await page.keyboard.type("select 2 as value", { delay: 20 });
    await page.keyboard.press("Escape");
    await page.keyboard.press("Shift+Alt+F");
    await expect(editor.locator(".view-lines")).toContainText(
      /select\s+2\s+as\s+value/i,
    );
    await expect(editor.locator(".view-line")).toHaveCount(2);
    await page
      .getByRole("button", { name: "caret-right Run", exact: true })
      .click();
    await waitRequest(r, "/editor/chart/run", "POST");
    const submitted = r.requests.find((request) =>
      request.path.endsWith("/editor/chart/run"),
    ).body;
    expect(JSON.parse(submitted).sql).toBe("select\n  2 as value");
    await expect(
      page.getByRole("columnheader", { name: "value", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "save Save", exact: true }).click();
    await waitRequest(r, "/chart/editor/submit", "POST");
    const saved = r.requests.find((request) =>
      request.path.endsWith("/chart/editor/submit"),
    );
    expect(JSON.parse(saved.body).new_sql).toBe("select\n  2 as value");
  },
);
interaction(
  "workflow-export-and-controls",
  "/construct/flow/canvas/?id=regression-flow",
  async (page) => {
    await expect(page.locator(".react-flow")).toBeVisible();
    await page.getByPlaceholder("Search node").fill("regression");
    await page.getByRole("switch").click();
    await page.getByRole("img", { name: "export", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByRole("radio", { name: "JSON", exact: true })
      .last()
      .check();
    const download = page.waitForEvent("download");
    await dialog.getByRole("button", { name: "确 认" }).click();
    const file = await download;
    expect(await file.failure()).toBeNull();
    const target = path.join(records, "workflow-export.json");
    await file.saveAs(target);
    const exported = JSON.parse(fs.readFileSync(target, "utf8"));
    expect(exported).toBeTruthy();
  },
);
interaction("evaluation-tabs-and-form", "/evaluation/", async (page) => {
  await page.getByText("数据集", { exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByText("评测数据", { exact: true }).click();
  await page.getByRole("button", { name: "发起评测" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
});

interaction(
  "shared-zero-step-replay",
  "/share/regression-share/",
  async (page) => {
    const answer = page.getByText("PR3277_SHARE_OK", { exact: true }).first();
    await expect(answer).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Thought:");
    await page.getByRole("button", { name: "reload 重新回放" }).click();
    await expect(answer).toBeVisible();
  },
);

interaction(
  "shared-json-replay",
  "/share/regression-json-share/",
  async (page) => {
    const content = JSON.stringify({ message: "PR3277_JSON_OK", lines: "first\nsecond" });
    const answer = page.getByText(content, { exact: true }).first();
    await expect(answer).toBeVisible();
    await page.reload();
    await expect(answer).toBeVisible();
    await page.getByRole("button", { name: "reload 重新回放" }).click();
    await expect(answer).toBeVisible();
  },
);
