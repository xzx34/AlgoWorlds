import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("the page presents AlgoWorlds as a standalone project", async ({ page }) => {
  await page.goto("./");

  await expect(page).toHaveTitle("AlgoWorlds | Weixin AI");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator(".site-brand")).toContainText("Weixin AI");
  await expect(page.locator(".team-name")).toContainText("Weixin AI");
  await expect(page.locator('.site-brand img[src$="weixin-mark.svg"]')).toBeVisible();
  await expect(page.locator('.team-name img[src$="weixin-mark.svg"]')).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "AlgoWorlds: Benchmarking Tool Use for Global Optimization in Algorithmic Worlds",
  );
  await expect(page.getByRole("heading", { name: "Abstract" })).toBeVisible();
  await expect(page.locator("#abstract p")).toHaveCount(1);
  await expect(page.getByText(/Tool-use benchmarks generally evaluate whether an agent completes a workflow/)).toBeVisible();
  await expect(page.locator("body")).not.toContainText("5,040");
  await expect(page.locator("body")).not.toContainText("3,876");
  await expect(page.locator("body")).not.toContainText("720 evaluations");
  await expect(page.locator(".hero-fact-strip")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Results", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Overall Performance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Benchmark Details" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Data Quality" })).toBeVisible();
  await expect(page.locator(".validation-grid > div")).toHaveCount(6);
  await expect(page.getByRole("heading", { name: "Benchmark Construction" })).toBeVisible();
  await expect(page.locator(".flow-list li")).toHaveCount(3);
  await expect(page.locator(".fact-item")).toHaveCount(6);
  await expect(page.getByRole("heading", { name: "Optimization Families" })).toBeVisible();

  const resultsHeadingOrder = await page.locator("#results h3").evaluateAll((headings) =>
    headings.map((heading) => heading.textContent?.trim()),
  );
  expect(resultsHeadingOrder).toEqual([
    "Sufficient information does not guarantee global optimality",
    "Overall Performance",
  ]);
  const articleOrder = await page.locator("main > section[id]").evaluateAll((sections) =>
    sections.map((section) => section.id),
  );
  expect(articleOrder).toEqual(["abstract", "results", "benchmark"]);

  await expect(page.locator(".leaderboard-table tbody tr")).toHaveCount(7);
  await expect(page.locator(".model-name img")).toHaveCount(0);
  await expect(page.locator(".provider-badge")).toHaveCount(7);
  await expect(page.locator(".provider-badge").first()).toHaveText("Anthropic");
  const modelOrder = await page.locator(".leaderboard-table .model-name > span:last-child").allTextContents();
  expect(modelOrder).toEqual([
    "Claude Opus 4.8",
    "GPT-5.6 Sol",
    "Claude Sonnet 5",
    "GPT-5.6 Terra",
    "GLM 5.2",
    "DeepSeek V4 Pro",
    "Qwen 3.5 Plus",
  ]);
  await expect(page.getByRole("row", { name: /Claude Opus 4\.8/ })).toContainText("38.61");
  await expect(page.getByRole("columnheader", { name: "Final-decision metrics" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Trajectory diagnostics" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Information sufficiency" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Exact optimality" })).toHaveAttribute("aria-sort", "descending");
  await expect(page.locator(".families-table tbody tr")).toHaveCount(10);
  await expect(page.locator(".metrics-table tbody tr")).toHaveCount(5);
  await expect(page.getByRole("columnheader", { name: "Rank" })).toHaveCount(0);

  const navigationLabels = await page.locator("nav[aria-label]").evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("aria-label")),
  );
  expect(new Set(navigationLabels).size).toBe(navigationLabels.length);

  const outcomeCounts = await page.locator(".outcome-segment").evaluateAll((segments) =>
    segments.map((segment) => segment.getAttribute("style")),
  );
  expect(outcomeCounts).toEqual(["--count: 269", "--count: 364", "--count: 14"]);
});

test("the hero and footer expose arXiv and one combined GitHub resource", async ({ page }) => {
  await page.goto("./");
  const resources = page.locator(".project-actions .project-link");

  await expect(resources).toHaveCount(2);
  await expect(page.getByRole("link", { name: "Paper (arXiv)" }).first()).toHaveAttribute(
    "href",
    "https://arxiv.org/abs/2608.29397",
  );
  await expect(page.getByRole("link", { name: "Code & Dataset" }).first()).toHaveAttribute(
    "href",
    "https://github.com/xzx34/AlgoWorlds",
  );
  await expect(page.getByRole("link", { name: "Code & Dataset" }).first().locator("svg")).toBeVisible();
  await expect(page.locator(".footer-links a")).toHaveCount(2);
  await expect(page.locator('a[href$=".pdf"]')).toHaveCount(0);
  await expect(page.locator(".language-link")).toHaveCount(0);

  await page.getByRole("link", { name: "Paper (arXiv)" }).first().focus();
  await expect(page.getByRole("link", { name: "Paper (arXiv)" }).first()).toBeFocused();

  for (const sourceOnlyPath of ["ASSETS.json", "brands/README.md", "figures/README.md"]) {
    const response = await page.request.get(new URL(sourceOnlyPath, page.url()).toString());
    expect(response.status(), sourceOnlyPath).toBe(404);
  }
});

test("the page uses the latest information-sufficiency paper figure", async ({ page }) => {
  await page.goto("./");
  const figure = page.locator(".paper-figure");
  const image = figure.locator("img");

  await expect(page.locator("figure")).toHaveCount(1);
  await expect(image).toBeVisible();
  await expect(image).toHaveAttribute("width", "2850");
  await expect(image).toHaveAttribute("height", "816");
  await expect(image).toHaveAttribute("alt", /information sufficiency/i);
  expect(await image.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBe(2850);
  await expect(figure).toContainText("Sufficient information does not guarantee global optimality.");
  await expect(figure).not.toContainText("Figure 1");
  await expect(figure.getByRole("link", { name: "View full-size figure" }).last()).toBeVisible();
  await expect(page.getByRole("region", { name: "Scroll horizontally to inspect the figure." })).toBeVisible();
  await expect(figure.locator("figcaption .paper-figure-hint")).toHaveCount(1);
});

test("desktop content retains the established 1088 pixel shell", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop-only assertion");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("./");

  const outerSelectors = [
    ".site-nav",
    ".masthead",
    "#abstract",
    ".paper-figure-section",
    "#benchmark",
    "#results",
    ".footer-content",
  ];
  const outerBoxes = await Promise.all(
    outerSelectors.map((selector) => page.locator(selector).boundingBox()),
  );
  for (const box of outerBoxes) {
    expect(box).not.toBeNull();
    expect(box?.x).toBeCloseTo(176, 0);
    expect(box?.width).toBeCloseTo(1088, 0);
  }

  const abstractBox = await page.locator(".abstract-prose").boundingBox();
  expect(abstractBox).not.toBeNull();
  expect(abstractBox?.width).toBeCloseTo(940, 0);
  expect(abstractBox?.x).toBeCloseTo(250, 0);
});

test("the page has no serious automated accessibility violations", async ({ page }) => {
  await page.goto("./");
  await page.waitForTimeout(700);
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});

test("reduced motion leaves all editorial content visible", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  const hidden = await page.locator("[data-reveal]").evaluateAll((elements) =>
    elements.filter((element) => {
      const style = getComputedStyle(element);
      return style.opacity === "0" || style.transform !== "none";
    }).length,
  );
  expect(hidden).toBe(0);
});

test("mobile layout contains wide content inside designated viewports", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("mobile"), "mobile-only assertion");
  await page.goto("./");
  await expect(page.locator(".site-links")).toBeVisible();
  const [brandBox, sectionLinksBox] = await Promise.all([
    page.locator(".site-brand").boundingBox(),
    page.locator(".site-links").boundingBox(),
  ]);
  expect(brandBox).not.toBeNull();
  expect(sectionLinksBox).not.toBeNull();
  expect(sectionLinksBox!.y).toBeGreaterThan(brandBox!.y);

  const dimensions = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);

  const table = page.locator(".table-region").last();
  await expect(table).toBeVisible();
  await table.focus();
  await expect(table).toBeFocused();

  const figureViewport = page.locator(".paper-figure-viewport");
  const figureDimensions = await figureViewport.evaluate((element) => ({
    client: element.clientWidth,
    scroll: element.scrollWidth,
  }));
  expect(figureDimensions.scroll).toBeGreaterThan(figureDimensions.client);
  await figureViewport.focus();
  await expect(figureViewport).toBeFocused();
});
