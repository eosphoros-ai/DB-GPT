const { test, expect } = require("@playwright/test");
const { envelope, responseFor } = require("./fixtures.cjs");

async function advance(page, milliseconds) {
  await page.clock.runFor(milliseconds);
  // The virtual browser clock does not drive network response delivery.
  await page.waitForTimeout(100);
}

async function openCopilot(
  page,
  { statuses = ["pending"], expiresIn = 900 } = {},
) {
  const polls = [];
  let starts = 0;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let data;
    if (url.pathname.endsWith("/github_copilot/auth/start")) {
      starts++;
      data = {
        device_code: `fixture-${starts}`,
        user_code: "TEST-CODE",
        verification_uri: "https://github.com/login/device",
        interval: 5,
        expires_in: expiresIn,
      };
    } else if (url.pathname.endsWith("/github_copilot/auth/poll")) {
      polls.push(url.searchParams.get("device_code"));
      const status = statuses[Math.min(polls.length - 1, statuses.length - 1)];
      if (status === "forbidden") {
        return route.fulfill({
          json: {
            success: false,
            data: null,
            err_code: "E000X",
            err_msg: "GitHub Copilot access was denied (HTTP 403)",
          },
        });
      }
      data = { status, enabled_models: status === "success" ? ["gpt-4o"] : [] };
    } else if (url.pathname.endsWith("/providers")) {
      data = [
        {
          provider: "proxy/github_copilot",
          name: "GitHub Copilot",
          models: [{ model: "gpt-4o", label: "GPT-4o" }],
          params: [],
          worker_type: "llm",
          proxy: true,
        },
      ];
    } else if (url.pathname.endsWith("/providers/config")) {
      data = {
        provider: "proxy/github_copilot",
        connected: false,
        enabled_models: [],
      };
    } else {
      data = responseFor(url, route.request().method()) ?? [];
    }
    await route.fulfill({ json: envelope(data) });
  });
  // All protocol responses are fixtures; no account or external OAuth request is used.
  await page.goto("/construct/models-config/");
  await expect(
    page.getByRole("heading", { name: "GitHub Copilot", exact: true }),
  ).toBeVisible();
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  await page.getByRole("button", { name: "连 接", exact: true }).click();
  await expect(page.getByPlaceholder("XXXX-XXXX")).toHaveValue("TEST-CODE");
  return { polls, starts: () => starts };
}

test("Copilot backs off on every slow_down and completes authorization", async ({
  page,
}) => {
  const { polls } = await openCopilot(page, {
    statuses: ["slow_down", "slow_down", "success"],
  });
  // Polls are due at 5s, then at least 15s and 30s. Leave margins for
  // network delivery while keeping each negative assertion before its deadline.
  await advance(page, 6000);
  await expect.poll(() => polls.length).toBe(1);
  await advance(page, 8000);
  expect(polls).toHaveLength(1);
  await advance(page, 3000);
  await expect.poll(() => polls.length).toBe(2);
  await advance(page, 12000);
  expect(polls).toHaveLength(2);
  await advance(page, 5000);
  await expect.poll(() => polls.length).toBe(3);
  await advance(page, 500);
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.getByRole("switch")).toBeChecked();
});

test("Copilot stops polling at the returned expiry", async ({ page }) => {
  const { polls } = await openCopilot(page, { expiresIn: 6 });
  await page.clock.runFor(10000);
  await expect(
    page.getByText("授权失败或已过期，请关闭后重试", { exact: true }),
  ).toBeVisible();
  const count = polls.length;
  await page.clock.runFor(30000);
  expect(polls).toHaveLength(count);
});

test("Copilot cancellation stops polling and reopening starts a new flow", async ({
  page,
}) => {
  const { polls, starts } = await openCopilot(page);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.clock.runFor(20000);
  expect(polls).toHaveLength(0);
  await page.getByRole("button", { name: "连 接", exact: true }).click();
  await expect(page.getByPlaceholder("XXXX-XXXX")).toHaveValue("TEST-CODE");
  expect(starts()).toBe(2);
  await page.clock.runFor(8000);
  await expect.poll(() => polls.length).toBe(1);
  expect(polls[0]).toBe("fixture-2");
});

test("Copilot shows access denial and does not mark the provider connected", async ({
  page,
}) => {
  const { polls } = await openCopilot(page, { statuses: ["forbidden"] });
  await page.clock.runFor(8000);
  await expect(page.getByRole("dialog")).toContainText(
    "GitHub Copilot access was denied (HTTP 403)",
  );
  await page.clock.runFor(30000);
  expect(polls).toHaveLength(1);
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("switch")).not.toBeChecked();
});
