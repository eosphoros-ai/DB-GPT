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
      commands: [{ name: '/analyze', skill: 'multi-step-analysis' }],
      recommended_questions: [
        {
          text: '生成 Walmart 销售分析报告',
          text_en: 'Generate a Walmart sales analysis report',
          command: '/analyze',
          database_name: 'Walmart_Sales',
        },
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

async function setup(page: Page, availableDatabases = databases, language = 'zh') {
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
              steps: [],
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
