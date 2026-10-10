const { test, expect } = require("@playwright/test");
const { envelope, responseFor } = require("./fixtures.cjs");

for (const failure of [
  {
    status: 400,
    json: { err_msg: "The file_path input is invalid." },
    message: "The file_path input is invalid.",
  },
  {
    status: 503,
    body: "Service unavailable",
    contentType: "text/html",
    message: "Request failed (503)",
  },
]) {
  test(`home example reports HTTP ${failure.status} instead of remaining in thinking state`, async ({
    page,
  }) => {
    const submissions = [];
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.route("**/api/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.pathname === "/api/v1/examples/use") {
        expect(request.postDataJSON()).toEqual({ example_id: "walmart_sales" });
        return route.fulfill({
          json: envelope("D:/uploads/001/Walmart_Sales.csv"),
        });
      }
      if (url.pathname === "/api/v1/chat/react-agent") {
        submissions.push(request.postDataJSON());
        const { message, ...response } = failure;
        return route.fulfill(response);
      }
      await route.fulfill({
        json: envelope(responseFor(url, request.method()) ?? []),
      });
    });
    await page.goto("/");
    await page
      .getByRole("heading", { name: "沃尔玛销售数据分析", exact: true })
      .click();
    await expect(
      page.getByText(failure.message, { exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByText(/DB-GPT 正在思考/)).toHaveCount(0);
    expect(submissions).toHaveLength(1);
    expect(submissions[0].ext_info.file_path).toBe(
      "D:/uploads/001/Walmart_Sales.csv",
    );
    await page
      .getByPlaceholder("向您的数据库提问，上传CSV，或生成报告...")
      .fill("Try again");
    await expect(
      page.getByRole("button", { name: "arrow-up", exact: true }),
    ).toBeEnabled();
    expect(pageErrors).toEqual([]);
  });
}
