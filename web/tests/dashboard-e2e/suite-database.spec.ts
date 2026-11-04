import { expect, test, type Page } from '@playwright/test';

const databases = [
  { id: 'olist', db_name: 'Olist_Ecommerce', type: 'sqlite' },
  { id: 'walmart', db_name: 'Walmart_Sales', type: 'sqlite' },
];
const suites = [
  {
    id: 1,
    name: 'db-query',
    display: '智能取数',
    scenario_id: 'query',
    version: '1.0.0',
    status: 'enabled',
    source: 'official',
    readme: '# 智能取数\n中文说明',
    readme_locales: { en: '# Smart Data Query\nEnglish plugin overview' },
    skill_details: [
      {
        name: 'nl2sql-precision',
        display: '精准 NL2SQL',
        display_en: 'NL2SQL Precision',
        description: '生成 SQL',
        description_en: 'Generate validated SQL',
      },
    ],
    manifest_snapshot: {
      display_en: 'Smart Data Query',
      description: '中文简介',
      description_en: 'Query data using validated read-only SQL',
      routing: { keywords: ['suite-routing-test'] },
      skills: ['nl2sql-precision'],
      commands: [
        {
          name: '/nl2sql',
          description: '自然语言取数',
          description_en: 'Natural-language data queries',
          skill: 'nl2sql-precision',
        },
        { name: '/schema', description: '查看表结构', skill: 'semantic-linking' },
        { name: '/export', description: '导出结果', skill: 'result-export' },
      ],
      recommended_questions: [
        {
          text: '近30天各品类客单价',
          text_en: 'Average order value by category over the last 30 days',
          hint_en: 'Use consistent metric definitions',
          command: '/nl2sql',
        },
        { text: '导出订单明细', command: '/export' },
      ],
    },
  },
  {
    id: 2,
    name: 'db-analysis',
    display: '智能分析',
    scenario_id: 'analysis',
    version: '1.0.0',
    status: 'enabled',
    manifest_snapshot: {
      display_en: 'Smart Data Analysis',
      commands: [
        { name: '/analyze', skill: 'multi-step-analysis' },
        {
          name: '/dashboard',
          skill: 'build-dashboard',
          prefill: '仪表板目标与受众 + 核心指标',
          prefill_en: 'Dashboard goal, audience and metrics',
        },
        { name: '/chart', skill: 'chart-advisor' },
        { name: '/attribute', skill: 'attribution-analysis' },
      ],
      recommended_questions: [
        {
          text: '生成 Walmart 销售分析报告',
          text_en: 'Generate a Walmart sales analysis report',
          command: '/analyze',
          database_name: 'Walmart_Sales',
        },
        {
          text: '构建 Walmart 销售经营大盘',
          text_en: 'Build a Walmart operational dashboard',
          command: '/dashboard',
          database_name: 'Walmart_Sales',
        },
        { text: '对比近 12 周订单占比趋势', command: '/chart' },
        { text: '哪些渠道拉动了增量', command: '/attribute' },
      ],
    },
  },
  {
    id: 3,
    name: 'mysql-ops-expert',
    display: 'MySQL 运维专家',
    scenario_id: 'expert',
    version: '1.0.0',
    status: 'enabled',
    manifest_snapshot: {
      display_en: 'MySQL Operations Expert',
      package_format: 'qwenwork-plugin',
      context_defaults: { datasource: 'optional' },
      commands: [
        {
          name: '/SQL 体检',
          display_en: '/SQL Doctor',
          aliases: ['/SQL Doctor'],
          skill: 'mysql-sql-doctor',
          description: '诊断 SQL',
          description_en: 'Diagnose SQL',
        },
      ],
    },
  },
];

function bindingEvent(send: Record<string, any>) {
  const native = send.ext_info.suite === 'mysql-ops-expert';
  return {
    type: 'suite.bound',
    command: native ? '/SQL 体检' : send.ext_info.suite_command,
    command_skill: native ? 'mysql-sql-doctor' : 'semantic-linking',
    skill_loaded: true,
    documents: native
      ? [
          { path: 'skills/mysql-sql-doctor/SKILL.md', status: 'loaded', sha256: 'a'.repeat(64) },
          {
            path: 'skills/mysql-ops-knowledge/references/safe-execution-rules.md',
            status: 'loaded',
            sha256: 'b'.repeat(64),
          },
        ]
      : [],
  };
}

async function setup(page: Page, availableDatabases = databases, language = 'zh', queryPayload?: object) {
  const sends: Record<string, any>[] = [];
  await page.addInitScript(language => {
    localStorage.setItem('__db_gpt_lng_key', language);
    localStorage.setItem('__db_gpt_theme_key', 'light');
    localStorage.setItem('dbgpt-selected-model', 'deepseek-v4-flash');
  }, language);
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (pathname.endsWith('/model/types')) data = ['deepseek-v4-flash'];
    else if (pathname.endsWith('/datasources')) data = availableDatabases;
    else if (pathname.endsWith('/suites')) data = suites;
    else if (pathname.endsWith('/suites/db-query')) data = suites[0];
    else if (pathname.endsWith('/dialogue/messages/history')) {
      data = [
        { role: 'human', context: '旧消息', order: 1 },
        {
          role: 'view',
          context: JSON.stringify({ version: 2, type: 'react-agent', final_content: '旧回复', steps: [] }),
          order: 1,
        },
        ...sends.flatMap((send, index) => [
          { role: 'human', context: send.user_input, order: index + 2 },
          {
            role: 'view',
            context: JSON.stringify({
              version: 2,
              type: 'react-agent',
              final_content: '数据库绑定请求已收到。',
              steps: queryPayload
                ? [
                    {
                      id: 'query-step',
                      step: 1,
                      title: 'sql_query',
                      action: 'sql_query',
                      status: 'done',
                      outputs: [{ output_type: 'query', content: queryPayload }],
                    },
                  ]
                : [],
              suite_reference: {
                name: send.ext_info.suite,
                display: send.ext_info.suite_display,
                command: send.ext_info.suite_command,
              },
              suite_binding: bindingEvent(send),
            }),
            order: index + 2,
          },
        ]),
      ];
    } else if (pathname.endsWith('/chat/react-agent')) {
      sends.push(route.request().postDataJSON());
      return route.fulfill({
        contentType: 'text/event-stream',
        body: [
          ...(sends[sends.length - 1].ext_info.suite_command ? [bindingEvent(sends[sends.length - 1])] : []),
          ...(queryPayload
            ? [
                { type: 'step.start', id: 'query-step', step: 1, title: 'sql_query', action: 'sql_query' },
                { type: 'step.chunk', id: 'query-step', output_type: 'query', content: queryPayload },
                { type: 'step.done', id: 'query-step', status: 'done' },
              ]
            : []),
          { type: 'final', content: '数据库绑定请求已收到。' },
          { type: 'done' },
        ]
          .map(event => `data: ${JSON.stringify(event)}\n\n`)
          .join(''),
      });
    }
    return route.fulfill({ json: { success: true, data } });
  });
  await page.goto('/');
  await expect(
    page.getByRole('button', { name: language === 'en' ? 'Smart Data Query' : '智能取数', exact: true }),
  ).toBeVisible();
  return sends;
}

for (const language of ['zh', 'en']) {
  for (const narrow of [false, true]) {
    test(`composer suite menu selects and switches suites (${language}, ${narrow ? 'narrow' : 'desktop'})`, async ({
      page,
    }, testInfo) => {
      if (narrow) await page.setViewportSize({ width: 390, height: 844 });
      const sends = await setup(page, databases, language);
      await page
        .getByRole('button', { name: language === 'en' ? 'Smart Data Query' : '智能取数', exact: true })
        .click();
      await page
        .getByRole('button', {
          name: language === 'en' ? /Average order value by category/ : /近30天各品类客单价/,
        })
        .click();
      await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
      const input = page.locator('textarea').first();
      await input.fill('/nl2sql Analyze business performance');
      await page.getByTestId('composer-context-trigger').click();
      const suiteMenu = page.getByRole('menuitem', {
        name: language === 'en' ? /Expert suite/ : /专家套件/,
      });
      await suiteMenu.hover();
      const analysis = page.getByTestId('composer-suite-db-analysis');
      await expect(analysis).toBeVisible();
      expect((await suiteMenu.boundingBox())!.height).toBeLessThanOrEqual(48);
      await expect(page.getByTestId('composer-suite-db-query').locator('..').locator('..')).toHaveCSS(
        'background-color',
        'rgb(244, 244, 245)',
      );
      const box = await analysis.boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
      await page.screenshot({ path: testInfo.outputPath('home-suite-menu.png'), animations: 'disabled' });
      await analysis.click();
      await expect(input).toHaveValue('Analyze business performance');
      await expect(page.getByTestId('suite-composer-prefix')).toHaveText(
        language === 'en' ? 'Smart Data Analysis' : '智能分析',
      );
      await input.press('Enter');
      await expect.poll(() => sends.length).toBe(1);
      expect(sends[0].ext_info).toMatchObject({ suite: 'db-analysis', database_name: 'Olist_Ecommerce' });
      expect(sends[0].ext_info.suite_command).toBeUndefined();
      await expect(page.getByText('数据库绑定请求已收到。', { exact: true }).first()).toBeVisible();
      await page.getByTestId('composer-context-trigger').click();
      await page.getByRole('menuitem', { name: language === 'en' ? /Expert suite/ : /专家套件/ }).hover();
      await page.getByTestId('composer-suite-mysql-ops-expert').click();
      await expect(page.getByTestId('suite-composer-prefix')).toHaveText(
        language === 'en' ? 'MySQL Operations Expert' : 'MySQL 运维专家',
      );
      await page.locator('textarea').first().fill('Check database health');
      await page.locator('textarea').first().press('Enter');
      await expect.poll(() => sends.length).toBe(2);
      expect(sends[1].ext_info.suite).toBe('mysql-ops-expert');
      expect(sends[1].ext_info.suite_command).toBeUndefined();
      // Earlier turns are collapsed by the conversation UI; the visible
      // current turn must show the suite actually carried by its request.
      await expect(page.getByTestId('message-suite-reference').last()).toContainText(
        language === 'en' ? 'MySQL Operations Expert' : 'MySQL 运维专家',
      );
      await page.reload();
      await expect(page.getByTestId('suite-composer-prefix')).toHaveText(
        language === 'en' ? 'MySQL Operations Expert' : 'MySQL 运维专家',
      );
      await page.evaluate(() => document.documentElement.classList.add('dark'));
      await page.getByTestId('composer-context-trigger').click();
      await page.getByRole('menuitem', { name: language === 'en' ? /Expert suite/ : /专家套件/ }).hover();
      await expect(page.getByTestId('composer-suite-mysql-ops-expert').locator('[data-icon="check"]')).toBeVisible();
      await expect(page.getByRole('menuitem', { name: language === 'en' ? 'View suites' : '查看套件' })).toHaveCSS(
        'color',
        'rgb(229, 230, 235)',
      );
      await page.screenshot({
        path: testInfo.outputPath('conversation-suite-menu-dark.png'),
        animations: 'disabled',
      });
      const manageSuites = page.getByRole('menuitem', { name: language === 'en' ? 'View suites' : '查看套件' });
      await manageSuites.focus();
      await manageSuites.press('Enter');
      await expect(page).toHaveURL(/\/construct\/suites/, { timeout: 60_000 });
    });
  }

  test(`native batch displays separate tool inputs and results (${language})`, async ({ page }) => {
    await setup(page, databases, language);
    const results = [
      {
        name: 'semantic_search_metrics',
        success: true,
        observation: JSON.stringify({
          source: 'semantic_center',
          items: [{ metric_name: 'GMV', formula: 'SUM(price)' }],
        }),
      },
      {
        name: 'sql_query',
        success: true,
        observation: JSON.stringify({
          chunks: [
            {
              output_type: 'query',
              content: {
                sql: 'SELECT 77 AS sales',
                columns: ['sales'],
                rows: [[77]],
                row_count: 1,
                db_name: 'Olist_Ecommerce',
              },
            },
          ],
        }),
      },
    ];
    await page.route('**/api/v1/chat/dialogue/messages/history*', route =>
      route.fulfill({
        json: {
          success: true,
          data: [
            { role: 'human', context: '有哪些业务指标', order: 1 },
            {
              role: 'view',
              order: 1,
              context: JSON.stringify({
                version: 2,
                type: 'react-agent',
                final_content: 'Metrics loaded',
                steps: [
                  {
                    id: 'batch',
                    step: 1,
                    title: 'semantic_search_metrics, sql_query',
                    action: 'semantic_search_metrics, sql_query',
                    action_input: JSON.stringify([{ query: '业务指标', limit: 50 }, { sql: 'SELECT 77 AS sales' }]),
                    status: 'done',
                    outputs: [{ output_type: 'text', content: JSON.stringify(results) }],
                  },
                ],
              }),
            },
          ],
        },
      }),
    );
    await page.goto('/?id=native-batch-history');
    const metrics = page.getByRole('button', { name: /semantic_search_metrics/ });
    const sql = page.getByRole('button', { name: /sql_query/ });
    await expect(metrics).toHaveCount(1);
    await expect(sql).toHaveCount(1);
    await expect(metrics).not.toContainText('SELECT');
    await expect(sql).not.toContainText('业务指标');
    await metrics.click();
    await expect(metrics.locator('..')).toContainText('"metric_name": "GMV"');
    await expect(metrics.locator('..').locator('table')).toHaveCount(0);
    await sql.click();
    await expect(sql.locator('..').locator('pre')).toHaveText('SELECT 77 AS sales');
    await expect(sql.locator('..').getByRole('cell', { name: '77', exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('button', { name: /semantic_search_metrics/ })).toHaveCount(1);
    await expect(page.getByRole('button', { name: /sql_query/ })).toHaveCount(1);
  });

  test(`historical SQL group expands each query and result (${language})`, async ({ page }) => {
    await setup(page, databases, language);
    await page.route('**/api/v1/chat/dialogue/messages/history*', route =>
      route.fulfill({
        json: {
          success: true,
          data: [
            { role: 'human', context: 'Query sales', order: 1 },
            {
              role: 'view',
              order: 1,
              context: JSON.stringify({
                version: 2,
                type: 'react-agent',
                final_content: 'Queries completed',
                steps: [111, 222].map((value, index) => ({
                  id: `query-${index}`,
                  step: index + 1,
                  title: 'sql_query',
                  action: 'sql_query',
                  status: 'done',
                  outputs: [
                    {
                      output_type: 'query',
                      content: {
                        sql: `SELECT ${value} AS sales`,
                        columns: ['sales'],
                        rows: [[value]],
                        row_count: 1,
                        db_name: 'Walmart_Sales',
                      },
                    },
                  ],
                })),
              }),
            },
          ],
        },
      }),
    );
    await page.goto('/?id=timeline-sql-history');
    const group = page.getByRole('button', { name: /sql_query/ }).first();
    await expect(group).toHaveAttribute('aria-expanded', 'false');
    await group.click();
    const rows = page.getByRole('button', { name: /sql_query/ });
    await expect(rows).toHaveCount(3);
    for (const [index, value] of [111, 222].entries()) {
      const row = rows.nth(index + 1);
      await row.click();
      const body = row.locator('..');
      await expect(body.locator('pre')).toHaveText(`SELECT ${value} AS sales`);
      await expect(body.getByRole('cell', { name: String(value), exact: true })).toBeVisible();
      await row.click();
      await expect(body.locator('table')).toHaveCount(0);
    }
    await page.reload();
    await expect(page.getByRole('button', { name: /sql_query/ })).toHaveCount(1);
    await page.getByRole('button', { name: /sql_query/ }).click();
    await page
      .getByRole('button', { name: /sql_query/ })
      .nth(1)
      .press('Enter');
    await expect(page.getByRole('button', { name: /sql_query/ }).nth(1)).toHaveAttribute('aria-expanded', 'true');
  });

  test(`dashboard plan survives reload and confirms generation (${language})`, async ({ page }) => {
    await setup(page, databases, language);
    const plan = {
      dashboard_id: 'test-dashboard',
      source_turn_id: 'test-turn',
      title: 'Walmart weekly sales',
      data_source_id: 'Walmart_Sales',
      total_widgets: 1,
      current_revision: 1,
      status: 'awaiting_confirmation',
      confirmation_prompt: '[[confirm-dashboard:test-dashboard]] revision 1',
      plan: { metrics: ['Sales'], widgets: [{ id: 'sales', title: 'Weekly sales', type: 'line' }] },
    };
    let generated = false;
    await page.route('**/api/v1/dashboards/test-dashboard**', route =>
      route.fulfill({
        json: {
          success: true,
          data: route.request().method() === 'POST' ? { widgets: {} } : { schema: { widgets: [], metric_context: {} } },
        },
      }),
    );
    await page.route('**/api/v1/chat/dialogue/messages/history*', route =>
      route.fulfill({
        json: {
          success: true,
          data: [
            { role: 'human', context: 'Build dashboard', order: 1 },
            {
              role: 'view',
              order: 1,
              context: JSON.stringify({
                version: 2,
                type: 'react-agent',
                final_content: 'Plan ready',
                steps: [],
                dashboard_refs: [
                  generated ? { ...plan, status: 'draft', editor_path: '/dashboards/test-dashboard' } : plan,
                ],
              }),
            },
          ],
        },
      }),
    );
    await page.route('**/api/v1/chat/react-agent', route => {
      const send = route.request().postDataJSON();
      expect(send.ext_info).toMatchObject({
        suite: 'db-analysis',
        suite_command: '/dashboard',
        creation_mode: 'dashboard',
        database_name: 'Walmart_Sales',
      });
      expect(send.user_input).toContain('[[confirm-dashboard:test-dashboard]]');
      generated = true;
      return route.fulfill({
        contentType: 'text/event-stream',
        body: [
          { ...plan, type: 'dashboard.generation.started' },
          { ...plan, type: 'dashboard.widget.validated', widget_id: 'sales' },
          { ...plan, type: 'dashboard.created', validated_widgets: 1, editor_path: '/dashboards/test-dashboard' },
          { type: 'final', content: 'Dashboard generated' },
          { type: 'done' },
        ]
          .map(event => `data: ${JSON.stringify(event)}\n\n`)
          .join(''),
      });
    });
    await page.goto('/?id=dashboard-test-conversation');
    const card = page.getByTestId('chat-dashboard-card');
    await expect(card).toContainText('Weekly sales');
    await page.reload();
    await card
      .getByRole('button', { name: language === 'en' ? 'Confirm and generate dashboard' : '确认并生成看板' })
      .click();
    await expect(card).toHaveCount(1);
    await expect(page.getByTestId('dashboard-artifact-preview')).toBeVisible();
    await expect(
      page.getByTestId('dashboard-artifact-preview').getByRole('button', {
        name: language === 'en' ? 'Open full dashboard' : '打开完整看板',
      }),
    ).toBeVisible();
    await expect(card.getByRole('button', { name: language === 'en' ? 'View dashboard' : '查看看板' })).toBeVisible();
    await page.reload();
    await expect(card.getByRole('button', { name: language === 'en' ? 'View dashboard' : '查看看板' })).toBeVisible();
  });
}

test('generic suite examples select a database and send it with the suite', async ({ page }) => {
  const sends = await setup(page);
  const example = page.getByRole('button', { name: /近30天各品类客单价/ });
  await expect(example).toContainText('数据库：请选择数据库');
  await expect(example).toContainText('指令：/nl2sql');
  await example.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
  await expect(example).toContainText('数据库：Olist_Ecommerce');
  await expect(page.getByTestId('suite-composer-prefix')).toHaveText('智能取数 · /nl2sql');
  await expect(page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...')).toHaveValue('近30天各品类客单价');
  await page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...').press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({
    suite: 'db-query',
    suite_command: '/nl2sql',
    database_name: 'Olist_Ecommerce',
    database_type: 'sqlite',
  });
  expect(sends[0].user_input).toBe('[Database: Olist_Ecommerce] 近30天各品类客单价');
  await expect(page.getByTestId('message-suite-reference')).toContainText('智能取数 · /nl2sql');
  await expect(page.getByTestId('message-suite-reference').locator('[data-icon="suite-hammer"]')).toBeVisible();
});

for (const language of ['zh', 'en']) {
  test(`analysis dashboard example carries command, skill and database (${language})`, async ({ page }) => {
    const sends = await setup(page, databases, language);
    await page
      .getByRole('button', {
        name: language === 'en' ? 'Smart Data Analysis' : '智能分析',
        exact: true,
      })
      .click();
    const example = page.getByRole('button', {
      name: language === 'en' ? /Build a Walmart operational dashboard/ : /构建 Walmart 销售经营大盘/,
    });
    await expect(example).toContainText('/dashboard');
    await example.click();
    await expect(page.getByTestId('suite-composer-prefix')).toContainText('/dashboard');
    await page.locator('textarea').first().press('Enter');
    await expect.poll(() => sends.length).toBe(1);
    expect(sends[0].ext_info).toMatchObject({
      suite: 'db-analysis',
      suite_command: '/dashboard',
      database_name: 'Walmart_Sales',
    });
    await expect(page.getByTestId('message-suite-reference')).toContainText('/dashboard');
  });
}

test('analysis trend and attribution examples each bind their own command', async ({ page }) => {
  await setup(page);
  await page.getByRole('button', { name: '智能分析', exact: true }).click();
  for (const [question, command] of [
    ['对比近 12 周订单占比趋势', '/chart'],
    ['哪些渠道拉动了增量', '/attribute'],
  ]) {
    const example = page.getByRole('button', { name: new RegExp(question) });
    await expect(example).toContainText(command);
    await example.click();
    if (await page.getByRole('dialog').isVisible()) {
      await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
    }
    await expect(page.getByTestId('suite-composer-prefix')).toContainText(command);
  }
});

test('smart query artifacts expose SQL, result and execution record live and after reload', async ({ page }) => {
  await setup(page, databases, 'zh', {
    sql: 'SELECT 42 AS answer',
    columns: ['answer'],
    rows: [[42]],
    row_count: 1,
    truncated: false,
    db_name: 'Olist_Ecommerce',
    execution: {
      status: 'succeeded',
      started_at: '2026-10-27T06:00:00+00:00',
      duration_ms: 123,
      tool: 'sql_query',
      artifact_id: 'test-query-record',
    },
  });
  await page.getByRole('button', { name: /近30天各品类客单价/ }).click();
  await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
  await page.locator('textarea').first().press('Enter');
  const artifact = page.getByTestId('query-artifact').first();
  await expect(artifact).toContainText('取数产物');
  await expect(artifact.locator('pre')).toContainText('SELECT 42 AS answer');
  await expect(artifact.getByRole('columnheader', { name: 'answer' })).toBeVisible();
  await expect(artifact.getByRole('cell', { name: '42', exact: true })).toBeVisible();
  await expect(artifact.getByTestId('query-execution-record')).toContainText('执行成功');
  await expect(artifact.getByTestId('query-execution-record')).toContainText('123 ms');
  await expect(page).toHaveURL(/\bid=/);
  await page.reload();
  await expect(artifact.getByTestId('query-execution-record')).toContainText('test-query-record');
  await expect(artifact.getByTestId('query-execution-record')).toContainText('Olist_Ecommerce');
  await expect(artifact.getByRole('cell', { name: '42', exact: true })).toBeVisible();
  await page.getByRole('button', { name: /会话产物/ }).click();
  await page.getByRole('button', { name: /查询结果 · 1 行/ }).click();
  const preview = page.getByTestId('query-artifact').last();
  await expect(preview.getByTestId('query-execution-record')).toBeVisible();
  await expect(preview.getByRole('columnheader', { name: 'answer' })).toBeVisible();
});

test('English plugins list and detail render localized content and search', async ({ page }) => {
  await setup(page, databases, 'en');
  await page.goto('/construct/suites/');
  await expect(page.getByRole('heading', { name: /Plugins$/ })).toBeVisible();
  await expect(page.getByText('Query data using validated read-only SQL')).toBeVisible();
  await page.getByPlaceholder('Search plugins…').fill('Smart Data Query');
  await page
    .locator('span')
    .filter({ hasText: /^Smart Data Query$/ })
    .click();
  await expect(page.getByRole('button', { name: /\/nl2sql.*Natural-language data queries/ })).toBeVisible();
  await expect(page.getByText('Generate validated SQL', { exact: true })).toBeVisible();
  await expect(page.getByTestId('suite-readme')).toContainText('English plugin overview');
  await expect(page.getByTestId('suite-readme')).not.toContainText('中文说明');
});

for (const path of ['/', '/construct/suites/']) {
  test(`language switching refreshes stale plugin metadata on ${path}`, async ({ page }) => {
    await setup(page);
    let refreshed = false;
    let requests = 0;
    await page.route('**/api/v1/suites', route => {
      requests += 1;
      const data = refreshed
        ? suites
        : suites.map(suite => ({
            ...suite,
            skill_details: [],
            manifest_snapshot: {
              ...suite.manifest_snapshot,
              description_en: undefined,
              recommended_questions: suite.manifest_snapshot.recommended_questions?.map(question => ({
                ...question,
                text_en: undefined,
              })),
            },
          }));
      return route.fulfill({ json: { success: true, data } });
    });
    await page.goto(path);
    await expect.poll(() => requests).toBeGreaterThan(0);
    const previousRequests = requests;
    refreshed = true;
    await page.locator('[aria-label="global"]').click();
    await expect.poll(() => requests).toBeGreaterThan(previousRequests);
    if (path === '/') {
      await expect(page.getByRole('button', { name: /Average order value by category/ })).toBeVisible();
    } else {
      await expect(page.getByText('Query data using validated read-only SQL')).toBeVisible();
      await expect(page.getByText('NL2SQL Precision', { exact: true })).toBeVisible();
      await expect(page.getByText('中文简介', { exact: true })).toHaveCount(0);
    }
  });
}

test('English examples keep database and canonical command bindings', async ({ page }) => {
  const sends = await setup(page, databases, 'en');
  await page.getByRole('button', { name: 'Smart Data Analysis', exact: true }).click();
  await page.getByRole('button', { name: /Generate a Walmart sales analysis report/ }).click();
  await expect(page.getByTestId('suite-composer-prefix')).toContainText('Smart Data Analysis · /analyze');
  await page.locator('textarea').first().press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({
    suite: 'db-analysis',
    suite_command: '/analyze',
    database_name: 'Walmart_Sales',
  });
  expect(sends[0].user_input).toBe('[Database: Walmart_Sales] Generate a Walmart sales analysis report');
});

test('English native command labels send the original canonical command', async ({ page }) => {
  const sends = await setup(page, [], 'en');
  await page.getByRole('button', { name: 'MySQL Operations Expert', exact: true }).click();
  await page.getByRole('button', { name: '/SQL Doctor', exact: true }).click();
  await expect(page.getByTestId('suite-composer-prefix')).toHaveText('MySQL Operations Expert · /SQL Doctor');
  await page.locator('textarea').first().fill('SELECT * FROM orders');
  await page.locator('textarea').first().press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({ suite: 'mysql-ops-expert', suite_command: '/SQL 体检' });
});

test('sent suite references keep their command when editing and reopening history', async ({ page }, testInfo) => {
  await setup(page);
  await page.getByRole('button', { name: /近30天各品类客单价/ }).click();
  await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
  await page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...').press('Enter');
  const reference = page.getByTestId('message-suite-reference');
  await expect(reference).toContainText('智能取数 · /nl2sql');
  await expect(page.getByText('数据库绑定请求已收到。', { exact: true }).first()).toBeVisible();
  await expect(page).toHaveURL(/\bid=/);
  // Typing another shortcut must not relabel the already sent message.
  await page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...').fill('/schema 查看表结构');
  await expect(reference).toContainText('智能取数 · /nl2sql');
  await page.screenshot({ path: testInfo.outputPath('expert-suite-message-reference.png') });
  await page.reload();
  await expect(reference).toHaveCount(1);
  await expect(reference).toContainText('智能取数 · /nl2sql');
  await expect(reference.locator('[data-icon="suite-hammer"]')).toBeVisible();
});

test('named examples switch away from the previous database before sending', async ({ page }) => {
  const sends = await setup(page);
  await page.getByRole('button', { name: /近30天各品类客单价/ }).click();
  await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
  await page.getByRole('button', { name: '智能分析', exact: true }).click();
  const example = page.getByRole('button', { name: /生成 Walmart 销售分析报告/ });
  await expect(example).toContainText('数据库：Walmart_Sales');
  await example.click();
  await expect(page.getByTestId('suite-composer-prefix')).toHaveText('智能分析 · /analyze');
  await page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...').press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({
    suite: 'db-analysis',
    suite_command: '/analyze',
    database_name: 'Walmart_Sales',
    database_type: 'sqlite',
  });
  expect(sends[0].user_input).toBe('[Database: Walmart_Sales] 生成 Walmart 销售分析报告');
});

test('a selected shortcut persists while editing and reaches the send payload', async ({ page }) => {
  const sends = await setup(page);
  await page.getByRole('button', { name: /近30天各品类客单价/ }).click();
  await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
  await page.getByRole('button', { name: '/schema', exact: true }).click();
  const input = page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...');
  await input.fill('查看 orders 表结构');
  await expect(page.getByTestId('suite-composer-prefix')).toHaveText('智能取数 · /schema');
  await input.press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({ suite: 'db-query', suite_command: '/schema' });
  expect(sends[0].user_input).toBe('[Database: Olist_Ecommerce] 查看 orders 表结构');
  await expect(page.getByText('指令 /schema · 知识技能 semantic-linking 已加载')).toBeVisible();
});

test('an export example replaces a previous command without another command click', async ({ page }) => {
  const sends = await setup(page);
  await page.getByRole('button', { name: '/schema', exact: true }).click();
  const example = page.getByRole('button', { name: /导出订单明细/ });
  await expect(example).toContainText('指令：/export');
  await example.click();
  await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
  await expect(page.getByTestId('suite-composer-prefix')).toHaveText('智能取数 · /export');
  await page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...').press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({ suite: 'db-query', suite_command: '/export' });
});

test('suite detail shortcut opens the composer with the command selected', async ({ page }) => {
  await setup(page);
  await page.goto('/construct/suites/');
  await page
    .locator('span')
    .filter({ hasText: /^智能取数$/ })
    .click();
  await page.getByRole('button', { name: /\/schema.*查看表结构/ }).click();
  await expect(page.getByTestId('suite-composer-prefix')).toHaveText('智能取数 · /schema');
});

test('a missing named database clears the stale selection and blocks sending', async ({ page }) => {
  const sends = await setup(page, [databases[0]]);
  await page.getByRole('button', { name: /近30天各品类客单价/ }).click();
  await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
  await page.getByRole('button', { name: '智能分析', exact: true }).click();
  await page.getByRole('button', { name: /生成 Walmart 销售分析报告/ }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('示例数据库“Walmart_Sales”尚未连接，请先连接该数据库')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click();
  await page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...').press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  expect(sends).toHaveLength(0);
});

test('native plugin supports spaced aliases without a database and restores loaded references', async ({ page }) => {
  const sends = await setup(page, []);
  await page.getByRole('button', { name: 'MySQL 运维专家', exact: true }).click();
  await expect(page.getByRole('button', { name: '/SQL 体检', exact: true })).toBeVisible();
  const input = page.getByPlaceholder('向您的数据库提问，上传CSV，或生成报告...');
  await input.fill('/SQL Doctor SELECT * FROM orders');
  await expect(page.getByTestId('suite-composer-prefix')).toHaveText('MySQL 运维专家 · /SQL 体检');
  await input.press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({ suite: 'mysql-ops-expert', suite_command: '/SQL 体检' });
  expect(sends[0].ext_info.database_name).toBeUndefined();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByTestId('suite-loaded-document')).toHaveCount(2);
  await expect(page.getByText('指令 /SQL 体检 · 知识技能 mysql-sql-doctor 已加载')).toBeVisible();
  await expect(page).toHaveURL(/\bid=/);
  await page.reload();
  await expect(page.getByTestId('suite-loaded-document')).toHaveCount(2);
  await expect(page.getByTestId('suite-loaded-document').last()).toContainText('safe-execution-rules.md');
  await expect(page.getByText('指令 /SQL 体检 · 知识技能 mysql-sql-doctor 已加载')).toBeVisible();
});

for (const language of ['zh', 'en']) {
  for (const narrow of [false, true]) {
    test(`suite cancellation by mouse and keyboard (${language}, ${narrow ? 'narrow' : 'desktop'})`, async ({
      page,
    }) => {
      if (narrow) await page.setViewportSize({ width: 390, height: 844 });
      const sends = await setup(page, databases, language);
      const scene = page.getByRole('button', {
        name: language === 'en' ? 'Smart Data Query' : '智能取数',
        exact: true,
      });
      const prefix = page.getByTestId('suite-composer-prefix');
      const input = page.locator('textarea').first();
      await expect(prefix).toHaveCount(0);
      await scene.click();
      await page
        .getByRole('button', {
          name: language === 'en' ? /Average order value by category/ : /近30天各品类客单价/,
        })
        .click();
      await page.getByRole('dialog').getByText('Olist_Ecommerce', { exact: true }).click();
      await input.fill('/schema suite-routing-test keep this question');
      await page.getByTestId('suite-composer-remove').click();
      await expect(prefix).toHaveCount(0);
      await expect(scene).toHaveAttribute('aria-pressed', 'false');
      await expect(input).toHaveValue('suite-routing-test keep this question');
      await scene.click();
      await scene.click();
      await expect(prefix).toHaveCount(0);

      await scene.click();
      await input.fill('suite-routing-test text');
      await input.press('End');
      await input.press('Backspace');
      await expect(input).toHaveValue('suite-routing-test tex');
      await expect(prefix).toBeVisible();
      await input.evaluate(element => (element as HTMLTextAreaElement).setSelectionRange(0, 5));
      await input.press('Backspace');
      await expect(input).toHaveValue('-routing-test tex');
      await expect(prefix).toBeVisible();
      await input.evaluate(element => (element as HTMLTextAreaElement).setSelectionRange(0, 0));
      await input.dispatchEvent('keydown', { key: 'Backspace', isComposing: true });
      await expect(prefix).toBeVisible();
      await input.press('Backspace');
      await expect(prefix).toHaveCount(0);
      await expect(input).toHaveValue('-routing-test tex');

      await scene.click();
      await input.fill('');
      await input.press('Delete');
      await expect(prefix).toHaveCount(0);
      await scene.click();
      await page.getByTestId('suite-composer-remove').focus();
      await page.getByTestId('suite-composer-remove').press('Enter');
      await expect(prefix).toHaveCount(0);
      await input.fill('suite-routing-test keep database');
      await input.press('Enter');
      await expect.poll(() => sends.length).toBe(1);
      expect(sends[0].ext_info.database_name).toBe('Olist_Ecommerce');
      expect(sends[0].ext_info.suite).toBeUndefined();
      expect(sends[0].ext_info.suite_command).toBeUndefined();
      await expect(page.getByText('数据库绑定请求已收到。', { exact: true }).first()).toBeVisible();

      const selectNative = async () => {
        await page.getByTestId('composer-context-trigger').click();
        await page.getByRole('menuitem', { name: language === 'en' ? /Expert suite/ : /专家套件/ }).hover();
        await page.getByTestId('composer-suite-mysql-ops-expert').click();
        await expect(prefix).toBeVisible();
      };
      await selectNative();
      await input.fill('keep chat draft');
      await input.evaluate(element => (element as HTMLTextAreaElement).setSelectionRange(0, 0));
      await input.press('Delete');
      await expect(prefix).toHaveCount(0);
      await expect(input).toHaveValue('keep chat draft');
      await selectNative();
      await input.fill('');
      await input.press('Backspace');
      await expect(prefix).toHaveCount(0);
      await selectNative();
      await page.getByTestId('suite-composer-remove').click();
      await expect(prefix).toHaveCount(0);
      await selectNative();
      await page.getByTestId('composer-context-trigger').click();
      await page.getByRole('menuitem', { name: language === 'en' ? /Expert suite/ : /专家套件/ }).hover();
      await page.getByTestId('composer-suite-mysql-ops-expert').click();
      await expect(prefix).toHaveCount(0);
      await input.fill('suite-routing-test keep chat database');
      await input.press('Enter');
      await expect.poll(() => sends.length).toBe(2);
      expect(sends[1].ext_info.database_name).toBe('Olist_Ecommerce');
      expect(sends[1].ext_info.suite).toBeUndefined();
      expect(sends[1].ext_info.suite_command).toBeUndefined();
    });
  }
}
