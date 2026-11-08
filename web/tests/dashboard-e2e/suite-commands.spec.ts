import { expect, test, type Page } from '@playwright/test';
import type { SuiteItem } from '../../types/suite';

const financialSuite: SuiteItem = {
  id: 4,
  name: 'financial-analysis',
  display: '财报分析',
  scenario_id: 'financial',
  version: '1.0.0',
  source: 'official',
  status: 'enabled',
  manifest_snapshot: {
    context_defaults: { datasource: 'optional', harness_engine: 'dbgpt' },
    commands: [
      {
        name: '/读年报',
        aliases: ['/annual-report'],
        description: '上传年报 PDF，分析营收利润和现金流',
        prefill: '请分析这份年报的营收利润和现金流。',
        input_files: { min: 1, max: 1, types: ['application/pdf'] },
      },
      {
        name: '/财报对比',
        aliases: ['/compare-reports'],
        description: '上传多份财报，比较公司或报告期',
        prefill: '请比较这些财报的经营表现。',
        input_files: { min: 2, max: 5, types: ['application/pdf'] },
      },
    ],
    recommended_questions: [
      { text: '解读这份年报的现金流', command: '/读年报' },
      { text: '比较多份财报', command: '/财报对比' },
    ],
  },
};
const suites: SuiteItem[] = [
  ...['query', 'analysis', 'ops'].map((scene, index) => ({
    id: index + 1,
    name: `db-${scene}`,
    display: ['智能取数', '智能分析', '智能运维'][index],
    scenario_id: scene,
    version: '1.0.0',
    source: 'official',
    status: 'enabled',
    manifest_snapshot: { commands: [{ name: `/${scene}`, description: `数据库 ${scene}` }] },
  })),
  financialSuite,
];

async function setup(page: Page) {
  const sends: Record<string, any>[] = [];
  const files: Record<string, any>[] = [];
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('__db_gpt_theme_key', 'light');
  });
  await page.route('**/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (path.endsWith('/model/types')) data = ['qwen-plus'];
    else if (path.endsWith('/datasources')) data = [{ id: 'old-db', db_name: 'OldDatabase', type: 'sqlite' }];
    else if (path.endsWith('/suites')) data = suites;
    else if (path.endsWith('/skills/list')) {
      data = [{ id: 'old-skill', name: 'old-skill', description: '已有技能', type: 'official' }];
    } else if (path.endsWith('/agent/files/capabilities')) {
      data = {
        max_files_per_upload: 20,
        max_file_bytes: 104857600,
        max_upload_bytes: 524288000,
        max_owner_bytes: -1,
        upload_request_timeout_seconds: 180,
        upload_concurrency: 3,
        supported_extensions: ['.pdf', '.csv'],
      };
    } else if (path.endsWith('/agent/files')) {
      if (request.method() === 'POST') {
        const body = request.postDataBuffer()?.toString('utf8') || '';
        const name = /filename="([^"]+)"/.exec(body)?.[1] || 'annual.pdf';
        const snapshot = {
          file_id: `file-${files.length + 1}`,
          name,
          size: 32,
          media_type: name.endsWith('.pdf') ? 'application/pdf' : 'text/csv',
          kind: 'document',
          status: 'ready',
          ordinal: files.length,
        };
        files.push(snapshot);
        data = [snapshot];
      } else data = files;
    } else if (path.endsWith('/chat/react-agent')) {
      const send = request.postDataJSON();
      sends.push(send);
      return route.fulfill({
        contentType: 'text/event-stream',
        body: [
          {
            type: 'suite.bound',
            suite: send.ext_info.suite,
            command: send.ext_info.suite_command,
            command_skill: 'financial-report-analyzer',
            skill_loaded: true,
          },
          { type: 'final', content: '已收到测试请求。' },
          { type: 'done' },
        ]
          .map(event => `data: ${JSON.stringify(event)}\n\n`)
          .join(''),
      });
    } else if (path.endsWith('/dialogue/messages/history')) {
      data = sends.flatMap((send, index) => [
        { role: 'human', context: send.user_input, order: index + 1 },
        {
          role: 'view',
          order: index + 1,
          context: JSON.stringify({
            version: 2,
            type: 'react-agent',
            final_content: '已收到测试请求。',
            steps: [],
            suite_reference:
              !send.ext_info.suite_reset && send.ext_info.suite
                ? {
                    name: send.ext_info.suite,
                    display: '财报分析',
                    command: send.ext_info.suite_command,
                  }
                : null,
          }),
        },
      ]);
    }
    await route.fulfill({ json: { success: true, data } });
  });
  return { sends, files };
}

const pdf = (name: string) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nfixture\n%%EOF') });

async function uploadPdf(page: Page, name: string) {
  await page.getByTestId('composer-context-trigger').click();
  const chooser = page.waitForEvent('filechooser');
  await page.getByText('从本地文件添加', { exact: true }).click();
  await (await chooser).setFiles(pdf(name));
}

test('home and conversation slash menus bind financial commands and preserve uploaded materials', async ({ page }) => {
  const { sends, files } = await setup(page);
  await page.goto('/?database_name=OldDatabase');
  await expect(page.getByRole('button', { name: '财报分析', exact: true })).toBeVisible();
  await expect(page.getByText('OldDatabase', { exact: true }).first()).toBeVisible();
  await page.getByTestId('composer-context-trigger').click();
  await page.getByRole('menuitem', { name: /使用技能/ }).hover();
  await page.getByRole('menuitem', { name: /old-skill/ }).click();

  const input = page.locator('textarea').first();
  await input.fill('/');
  await expect(page.getByRole('listbox', { name: '专家套件命令' })).toBeVisible();
  await expect(page.getByRole('listbox').getByRole('group')).toHaveCount(4);
  await input.fill('/annual');
  await input.press('Enter');
  await expect(page.getByRole('listbox')).toHaveCount(0);
  await expect(input).toHaveValue('请分析这份年报的营收利润和现金流。');
  await expect(page.getByTestId('suite-composer-prefix')).toContainText('财报分析 · /读年报');
  await expect(page.getByText('OldDatabase', { exact: true })).toHaveCount(0);
  expect(sends).toHaveLength(0);

  await input.press('Enter');
  await expect(page.getByText('请先上传 1 份 PDF 文件，再开始任务。')).toBeVisible();
  expect(sends).toHaveLength(0);
  await uploadPdf(page, 'annual-2024.pdf');
  await expect.poll(() => files.length).toBe(1);
  await input.press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info).toMatchObject({
    suite: 'financial-analysis',
    suite_command: '/读年报',
    harness_engine: 'dbgpt',
    file_ids: ['file-1'],
  });
  expect(sends[0].ext_info.skill_id).toBeUndefined();
  expect(sends[0].ext_info.database_name).toBeUndefined();
  expect(sends[0].ext_info.knowledge_space_name).toBeUndefined();

  const conversationInput = page.locator('textarea').first();
  await conversationInput.fill('/compare');
  await expect(page.getByRole('option')).toHaveCount(1);
  await conversationInput.press('Enter');
  await expect(page.getByTestId('suite-composer-prefix')).toContainText('/财报对比');
  await expect(page.getByTestId('suite-material-guide')).toContainText('上传 2–5 份 PDF');
  await conversationInput.press('Enter');
  await expect(page.getByText('请先上传 2–5 份 PDF 文件，再开始任务。')).toBeVisible();
  expect(sends).toHaveLength(1);
  await uploadPdf(page, 'annual-2025.pdf');
  await expect.poll(() => files.length).toBe(2);
  await conversationInput.press('Enter');
  await expect.poll(() => sends.length).toBe(2);
  expect(sends[1].ext_info).toMatchObject({ suite_command: '/财报对比', file_ids: ['file-1', 'file-2'] });
});

test('suite detail links, home shortcuts and questions share the command context', async ({ page }) => {
  const { sends, files } = await setup(page);
  await page.goto('/?suite=financial-analysis&suite_command=%2Fcompare-reports');
  await expect(page.getByTestId('suite-composer-prefix')).toContainText('/财报对比');
  await expect(page.locator('textarea').first()).toHaveValue('请比较这些财报的经营表现。');
  await page.getByRole('button', { name: '/读年报', exact: true }).click();
  await expect(page.getByTestId('suite-material-guide')).toContainText('上传 1 份 PDF');
  await expect(page.locator('textarea').first()).toHaveValue('请分析这份年报的营收利润和现金流。');
  const readCard = page.getByRole('button', { name: '解读这份年报的现金流', exact: true });
  const compareCard = page.getByRole('button', { name: '比较多份财报', exact: true });
  await expect(readCard).toContainText('上传 1 份 PDF 文件');
  await expect(compareCard).toContainText('上传 2–5 份 PDF 文件');
  await expect(readCard).not.toContainText('请选择数据库');
  await expect(compareCard).not.toContainText('请选择数据库');
  await readCard.click();
  await expect(page.locator('textarea').first()).toHaveValue('解读这份年报的现金流');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(sends).toHaveLength(0);
  const chooser = page.waitForEvent('filechooser');
  await page.getByTestId('suite-upload-files').click();
  const fileChooser = await chooser;
  expect(await fileChooser.element().getAttribute('accept')).toBe('application/pdf');
  await fileChooser.setFiles(pdf('annual.pdf'));
  await expect.poll(() => files.length).toBe(1);
  await page.locator('textarea').first().press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info.file_ids).toEqual(['file-1']);
  expect(sends[0].ext_info.database_name).toBeUndefined();
});

test('escape, Chinese composition and ordinary paths do not accidentally select or send', async ({ page }) => {
  const { sends } = await setup(page);
  await page.goto('/');
  await expect(page.getByRole('button', { name: '财报分析', exact: true })).toBeVisible();
  const input = page.locator('textarea').first();
  await input.fill('/');
  await expect(page.getByRole('listbox')).toBeVisible();
  await input.dispatchEvent('compositionstart');
  await input.dispatchEvent('keydown', { key: 'Enter', isComposing: true, keyCode: 229 });
  expect(sends).toHaveLength(0);
  await input.dispatchEvent('compositionend');
  await input.press('Escape');
  await expect(page.getByRole('listbox')).toHaveCount(0);
  await expect(input).toHaveValue('/');
  await input.fill('/tmp/report.pdf');
  await expect(page.getByRole('listbox')).toHaveCount(0);
  expect(sends).toHaveLength(0);
});

test('cancelling a suite clears its server pin and refresh does not restore an older selection', async ({ page }) => {
  const { sends, files } = await setup(page);
  await page.goto('/?suite=financial-analysis&suite_command=%2F读年报');
  await expect(page.getByTestId('suite-composer-prefix')).toContainText('/读年报');
  await uploadPdf(page, 'annual.pdf');
  await expect.poll(() => files.length).toBe(1);
  await page.locator('textarea').first().press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  await page.getByTestId('suite-composer-remove').click();
  await expect(page.getByTestId('suite-composer-prefix')).toHaveCount(0);
  await page.locator('textarea').first().fill('普通问题');
  await page.locator('textarea').first().press('Enter');
  await expect.poll(() => sends.length).toBe(2);
  expect(sends[1].ext_info.suite_reset).toBe(true);
  expect(sends[1].ext_info.suite).toBeUndefined();
  expect(sends[1].ext_info.suite_command).toBeUndefined();
  await page.reload();
  await expect(page.locator('textarea').first()).toBeVisible();
  await expect(page.getByText('普通问题', { exact: true })).toBeVisible();
  await expect(page.getByTestId('suite-composer-prefix')).toHaveCount(0);
});

test('new tasks clear the previous suite and command requirements', async ({ page }) => {
  const { sends } = await setup(page);
  await page.goto('/?suite=financial-analysis&suite_command=%2F财报对比');
  await expect(page.getByTestId('suite-composer-prefix')).toContainText('/财报对比');
  await page.getByText('新任务', { exact: true }).click();
  await expect(page.getByTestId('suite-composer-prefix')).toHaveCount(0);
  await expect(page.getByTestId('suite-material-guide')).toHaveCount(0);
  const input = page.locator('textarea').first();
  await input.fill('普通问题');
  await input.press('Enter');
  await expect.poll(() => sends.length).toBe(1);
  expect(sends[0].ext_info.suite).toBeUndefined();
  expect(sends[0].ext_info.suite_command).toBeUndefined();
  expect(sends[0].ext_info.suite_reset).toBeUndefined();
});
