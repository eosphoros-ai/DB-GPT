import { expect, type Page } from '@playwright/test';

/** Drive the scoped Dashboard entry and its actual data-source selector. */
export async function openDashboardCreation(page: Page, database?: string) {
  await page.goto('/dashboards/new/');
  await expect(page.getByRole('heading', { name: '新建看板', exact: true })).toBeVisible();
  if (database) {
    await page.getByRole('combobox', { name: '数据源', exact: true }).click();
    await page.getByTitle(database, { exact: true }).click();
  }
  return page.getByRole('textbox', { name: '分析需求', exact: true });
}
