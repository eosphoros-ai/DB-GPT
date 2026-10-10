const { test, expect } = require("@playwright/test");
const { envelope, responseFor } = require("./fixtures.cjs");

const fs = require("node:fs");
const { pathToFileURL } = require("node:url");

const pixel =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6dWQAAAAASUVORK5CYII=";
const reportHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>财报离线检查</title>
<style>h1 { color: rgb(10, 20, 30); }</style></head><body><h1>财报离线检查</h1><p>收入 123</p>
<picture><source srcset="/images/responsive.png"><img alt="chart" src="/images/offline.png" srcset="/images/responsive.png 2x"></picture>
<img alt="duplicate" src="/images/offline.png"><img alt="embedded" src="data:image/png;base64,${pixel}">
<script>document.body.dataset.reportReady = "yes";</script></body></html>`;

async function mockReportHistory(
  page,
  html,
  status = "completed",
  imageStatus = 200,
) {
  await page.route("**/images/**", (route) =>
    route.fulfill({
      status: imageStatus,
      contentType: "image/png",
      body: Buffer.from(pixel, "base64"),
    }),
  );
  await page.route("**/api/**", (route) => {
    const request = route.request(),
      url = new URL(request.url());
    if (url.pathname === "/api/v1/chat/dialogue/messages/history") {
      return route.fulfill({
        json: envelope([
          { role: "human", context: "生成财报", order: 0 },
          {
            role: "view",
            order: 1,
            context: JSON.stringify({
              version: 2,
              protocol_version: 2,
              type: "react-agent",
              status,
              final_content:
                status === "failed" ? "模型超时，请重试。" : "财报已生成。",
              steps: html
                ? [
                    {
                      id: "report",
                      action: "generate_html",
                      status: "done",
                      outputs: [{ output_type: "html", content: html }],
                    },
                  ]
                : [],
            }),
          },
        ]),
      });
    }
    return route.fulfill({
      json: envelope(responseFor(url, request.method()) ?? []),
    });
  });
}

test("report download embeds images and renders from disk with networking disabled", async ({
  page,
  browser,
}, testInfo) => {
  await mockReportHistory(page, reportHtml);
  await page.goto("/?id=offline-report");
  await page.getByText("Report.html", { exact: true }).first().click();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "download", exact: true })
    .first()
    .click();
  const download = await downloadPromise;
  expect(await download.failure()).toBeNull();
  const file = testInfo.outputPath("offline-report.html");
  await download.saveAs(file);
  const saved = fs.readFileSync(file, "utf8");
  expect(saved).not.toContain("/images/");
  const context = await browser.newContext({ offline: true });
  try {
    const offlinePage = await context.newPage(),
      requests = [],
      errors = [];
    offlinePage.on("request", (r) => {
      if (/^https?:/.test(r.url())) requests.push(r.url());
    });
    offlinePage.on("pageerror", (e) => errors.push(e.message));
    await offlinePage.goto(pathToFileURL(file).href);
    await expect(
      offlinePage.getByRole("heading", { name: "财报离线检查" }),
    ).toBeVisible();
    await expect(offlinePage.getByRole("heading")).toHaveCSS(
      "color",
      "rgb(10, 20, 30)",
    );
    await expect(offlinePage.locator("body")).toHaveAttribute(
      "data-report-ready",
      "yes",
    );
    await expect(offlinePage.locator("img")).toHaveCount(3);
    await expect
      .poll(() =>
        offlinePage
          .locator("img")
          .evaluateAll((imgs) =>
            imgs.every(
              (img) =>
                img.complete &&
                img.naturalWidth > 0 &&
                img.src.startsWith("data:image/"),
            ),
          ),
      )
      .toBe(true);
    expect(requests).toEqual([]);
    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});

test("report image failure shows an error without saving a broken HTML file", async ({
  page,
}) => {
  await mockReportHistory(page, reportHtml, "completed", 404);
  const downloads = [];
  page.on("download", (download) => downloads.push(download));
  await page.goto("/?id=missing-image");
  await page.getByText("Report.html", { exact: true }).first().click();
  await page
    .getByRole("button", { name: "download", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("报告图片下载失败，请检查连接后重试。", { exact: true }),
  ).toBeVisible();
  expect(downloads).toHaveLength(0);
});

for (const partial of [false, true]) {
  test(
    "model failure stays incomplete with partial output=" +
      partial +
      " and after reload",
    async ({ page }) => {
      await mockReportHistory(page, partial ? reportHtml : null, "failed");
      await page.route("**/api/v1/chat/react-agent", (route) =>
        route.fulfill({
          contentType: "text/event-stream",
          body: [
            ...(partial
              ? [
                  {
                    type: "step.start",
                    id: "report",
                    step: 1,
                    title: "生成报告",
                  },
                  {
                    type: "step.chunk",
                    id: "report",
                    output_type: "html",
                    content: reportHtml,
                  },
                ]
              : []),
            {
              type: "final",
              protocol_version: 2,
              status: "failed",
              content: "模型超时，请重试。",
              citations: [],
            },
            { type: "done" },
          ]
            .map((event) => "data: " + JSON.stringify(event) + "\n\n")
            .join(""),
        }),
      );
      await page.goto("/");
      await page
        .getByPlaceholder("向您的数据库提问，上传CSV，或生成报告...")
        .fill("生成技能");
      await page.getByRole("button", { name: "arrow-up", exact: true }).click();
      await expect(page.getByText("任务未完成", { exact: true })).toBeVisible();
      await expect(page.getByText("任务已完成", { exact: true })).toHaveCount(
        0,
      );
      await page.goto("/?id=failed-generation");
      await expect(page.getByText("任务未完成", { exact: true })).toBeVisible();
      await expect(page.getByText("任务已完成", { exact: true })).toHaveCount(
        0,
      );
    },
  );
}

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
