import { expect, test } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const backend = 'http://127.0.0.1:5670';

for (const engine of ['dbgpt', 'pi']) {
  test(`suite creation ${engine}: preview, edit, download, install and history`, async ({
    page,
    request,
  }, testInfo) => {
    const slug = `suite-creation-uat-${engine}-${Date.now()}`;
    const manifest = {
      name: slug,
      version: '1.0.0',
      displayNameCn: '周报办公专家',
      description: '根据项目材料生成周报和行动清单',
      skills: ['skills/report'],
      dbgpt: {
        sop: 'prompts/workflow.md',
        tools: { allow: [] },
        context_defaults: { datasource: 'optional' },
        required_resources: [],
        artifacts: [{ type: 'markdown', name: '周报' }],
        output_contract: { completion: '核对事实，提供风险与下一步' },
      },
    };
    const files = {
      '.qwenwork-plugin/plugin.json': JSON.stringify(manifest, null, 2),
      'README.md': '# 周报办公专家\n根据项目材料生成周报和行动清单。',
      'prompts/workflow.md': '# 工作流程\n阅读材料，生成周报，核对事实与责任人。',
      'skills/report/SKILL.md':
        '---\nname: report\nname_zh: 周报\ncommand: /周报\ndescription: "根据材料生成周报"\n---\n# 生成周报\n整理用户输入的事实，按进展、风险、负责人和下一步生成周报。逐条核对材料来源，对缺失内容明确标记。',
    };
    const created = await (
      await request.post(`${backend}/api/v1/suite-drafts`, { data: { requirement: '周报办公专家' } })
    ).json();
    expect(created.success).toBe(true);
    const draft = created.data;
    await request.patch(`${backend}/api/v1/suite-drafts/${draft.draft_id}`, { data: { expected_revision: 0, files } });
    const built = await (
      await request.post(`${backend}/api/v1/suite-drafts/${draft.draft_id}/build`, { data: { expected_revision: 1 } })
    ).json();
    expect(built.success).toBe(true);
    const artifact = built.data;
    const outputs =
      engine === 'dbgpt'
        ? [{ output_type: 'expert_suite', content: artifact }]
        : [
            {
              output_type: 'text',
              content: JSON.stringify({ success: true, chunks: [{ output_type: 'expert_suite', content: artifact }] }),
            },
          ];
    const sends: any[] = [];
    const steps = [
      {
        id: 'suite-package-build',
        title: '生成专家套件',
        action: 'suite_package_build',
        status: 'done',
        outputs,
      },
    ];
    await page.addInitScript(() => {
      localStorage.setItem('__db_gpt_lng_key', 'zh');
      localStorage.setItem('__db_gpt_theme_key', 'light');
    });
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url());
      const pathname = url.pathname.replace(/\/$/, '');
      if (/\/(suite-artifacts|suite-drafts|suites)(\/|$)/.test(pathname)) {
        return route.fulfill({ response: await route.fetch({ url: backend + pathname + url.search }) });
      }
      let data: any = [];
      if (pathname.endsWith('/model/types')) data = ['deepseek-v4-flash'];
      else if (pathname.endsWith('/dialogue/messages/history')) {
        data = sends.flatMap((send, index) => [
          { role: 'human', order: index + 1, context: send.user_input },
          {
            role: 'view',
            order: index + 1,
            context: JSON.stringify({
              version: 2,
              type: 'react-agent',
              final_content: '套件已生成，请在卡片上安装。',
              steps,
            }),
          },
        ]);
      } else if (pathname.endsWith('/chat/react-agent')) {
        sends.push(route.request().postDataJSON());
        return route.fulfill({
          contentType: 'text/event-stream',
          body: [
            { type: 'step.start', id: steps[0].id, title: steps[0].title, action: steps[0].action },
            ...outputs.map(output => ({ type: 'step.chunk', id: steps[0].id, ...output })),
            { type: 'step.done', id: steps[0].id, status: 'done' },
            { type: 'final', content: '套件已生成，请在卡片上安装。' },
            { type: 'done' },
          ]
            .map(event => `data: ${JSON.stringify(event)}\n\n`)
            .join(''),
        });
      }
      return route.fulfill({ json: { success: true, data } });
    });
    let installedPath = '';
    try {
      await page.goto('/construct/suites');
      await page.getByRole('link', { name: '智能创建', exact: true }).click();
      await expect(page.getByTestId('suite-creation-prefix')).toBeVisible();
      const input = page.locator('textarea').first();
      await input.fill('根据项目材料创建周报办公专家套件');
      await input.press('Enter');
      await expect(page.getByTestId('expert-suite-artifact').first()).toBeVisible();
      expect(sends[0].ext_info.creation_mode).toBe('expert_suite');
      expect(sends[0].ext_info.suite).toBeUndefined();
      await page.getByRole('button', { name: '预览与编辑', exact: true }).first().click();
      await expect(page.getByRole('textbox', { name: '文件正文' })).toHaveValue(files['README.md']);
      await page.getByRole('combobox', { name: '套件文件' }).selectOption('skills/report/SKILL.md');
      await expect(page.getByRole('textbox', { name: '文件正文' })).toHaveValue(files['skills/report/SKILL.md']);
      await page.screenshot({ path: testInfo.outputPath(`${engine}-suite-preview.png`), fullPage: true });
      await page.getByRole('button', { name: 'Close', exact: true }).click();
      const download = page.waitForEvent('download');
      await page.getByRole('button', { name: '下载套件', exact: true }).first().click();
      expect((await download).suggestedFilename()).toBe(`${slug}-1.0.0.zip`);
      await page.getByRole('button', { name: '一键安装', exact: true }).first().click();
      await expect(page.getByRole('button', { name: '用于新对话', exact: true }).first()).toBeVisible();
      const installed = (await (await request.get(`${backend}/api/v1/suites/${slug}`)).json()).data;
      installedPath = installed.package_path;
      expect(installed.status).toBe('enabled');
      await page.reload();
      await expect(page.getByTestId('expert-suite-artifact').first()).toBeVisible();
      await expect(page.getByRole('button', { name: '用于新对话', exact: true }).first()).toBeVisible();
      await page.getByRole('button', { name: '用于新对话', exact: true }).first().click();
      await expect(page.getByTestId('suite-composer-prefix')).toContainText('周报办公专家');
      await expect(page.getByTestId('suite-creation-prefix')).toHaveCount(0);
      await page.screenshot({ path: testInfo.outputPath(`${engine}-installed-suite.png`), fullPage: true });
    } finally {
      await request.delete(`${backend}/api/v1/suites/${slug}`);
      if (installedPath && path.basename(installedPath) === slug && slug.startsWith('suite-creation-uat-')) {
        await fs.rm(installedPath, { recursive: true });
      }
    }
  });
}

test('creation context cancels with mouse and keyboard while preserving the question', async ({ page }) => {
  await page.goto('/?creation_mode=expert_suite');
  const input = page.locator('textarea').first();
  await input.fill('保留用户已输入的需求');
  await page.getByTestId('suite-creation-remove').click();
  await expect(page.getByTestId('suite-creation-prefix')).toHaveCount(0);
  await expect(input).toHaveValue('保留用户已输入的需求');
  await page.goto('/?creation_mode=expert_suite');
  await input.fill('键盘取消后保留需求');
  await input.press('Home');
  await input.press('Backspace');
  await expect(page.getByTestId('suite-creation-prefix')).toHaveCount(0);
  await expect(input).toHaveValue('键盘取消后保留需求');
});

test('creation entry supports English on a narrow screen', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'en');
    localStorage.setItem('__db_gpt_theme_key', 'light');
  });
  await page.goto('/?creation_mode=expert_suite');
  await expect(page.getByTestId('suite-creation-prefix')).toContainText('Create expert suite');
  await expect(page.locator('textarea').first()).toHaveAttribute('placeholder', /Describe the suite/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('english-narrow-creation.png'), fullPage: true });
  await page.getByRole('button', { name: 'Cancel suite creation', exact: true }).click();
  await expect(page.getByTestId('suite-creation-prefix')).toHaveCount(0);
});
