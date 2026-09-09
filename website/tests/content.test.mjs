import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, readFile, readdir } from "node:fs/promises";
import { test } from "node:test";

/** @param {string} relative */
const read = (relative) => readFile(new URL(`../${relative}`, import.meta.url), "utf8");
/** @param {string} relative */
const readBytes = (relative) => readFile(new URL(`../${relative}`, import.meta.url));
/** @param {Buffer} bytes */
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

test("the publication results preserve the current benchmark design", async () => {
  const results = JSON.parse(await read("src/data/results.v1.json"));

  assert.equal(results.schemaVersion, "algoworlds_landing_results/4");
  assert.deepEqual(results.benchmark, {
    algorithmicWorlds: 240,
    evaluatedModels: 7,
    hiddenInstances: 120,
    instancesPerFamilyLevel: 3,
    optimizationFamilies: 10,
    pairedInterfaces: 2,
    publicName: "AlgoWorlds",
    trials: 3,
    validation: {
      channelCounterfactuals: 648,
      pairedHiddenInstances: 120,
      responseIsolationChecks: 1464,
      sufficientAcquisitionPlans: 480,
      uniqueOptima: 120,
    },
    workloadLevels: 4,
  });
  assert.equal(results.models.length, 7);
  assert.equal(results.models[0].name, "Claude Opus 4.8");
  assert.equal(results.models[0].exact.mean, 38.611111);
  assert.deepEqual(Object.keys(results.provenance), ["paperPdfSha256"]);
  assert.equal(
    results.provenance.paperPdfSha256,
    "1fff1553f1ee144c2adea438f9bcfcb77d87302c9d1fd41bae7f0d27618d105c",
  );
});

test("the paper-aligned information-sufficiency outcomes remain mutually exclusive", async () => {
  const { informationSufficiencyDiagnostic: diagnostic } = JSON.parse(
    await read("src/data/results.v1.json"),
  );

  assert.equal(
    diagnostic.exact +
      diagnostic.feasibleSuboptimal +
      diagnostic.infeasible +
      diagnostic.noSubmission +
      diagnostic.protocolOutcome,
    diagnostic.total,
  );
  assert.equal(diagnostic.total, 647);
  assert.equal(diagnostic.exact, 269);
  assert.equal(diagnostic.feasibleSuboptimal, 364);
  assert.equal(diagnostic.infeasible, 14);
  assert.equal(diagnostic.noSubmission, 0);
  assert.equal(diagnostic.protocolOutcome, 0);
});

test("the browser payload contains only the aggregate fields rendered by the page", async () => {
  const results = JSON.parse(await read("src/data/results.v1.json"));

  assert.deepEqual(Object.keys(results).sort(), [
    "benchmark",
    "informationSufficiencyDiagnostic",
    "models",
    "provenance",
    "schemaVersion",
    "tasks",
  ]);
  assert.deepEqual(Object.keys(results.models[0]).sort(), [
    "discoveryCoverage",
    "exact",
    "feasible",
    "id",
    "informationSufficiency",
    "name",
    "referenceUtility",
  ]);
  assert.deepEqual(Object.keys(results.tasks[0]).sort(), ["queryTools", "taskFamilyId"]);

  const serialized = JSON.stringify(results);
  for (const removed of [
    "byTaskFamily",
    "byWorkloadLevel",
    "conditionalOnInformationSufficiency",
    "introTrajectory",
    "pairedInterface",
    "panelInformationSufficiencyDiagnostic",
    "trajectory",
  ]) assert.doesNotMatch(serialized, new RegExp(`"${removed}"\\s*:`));
});

test("the visible copy follows the latest paper terminology", async () => {
  const copy = await read("src/content/copy.ts");
  const abstract = await read("src/components/AbstractSection.astro");

  assert.match(copy, /Sufficient information does not guarantee global optimality/);
  assert.match(copy, /Information sufficiency/);
  assert.match(copy, /joint normalization of the fact-revealing tool responses recovers at least one verified sufficient fact set/);
  assert.match(copy, /Across seven leading LLMs/);
  assert.match(copy, /For GPT-5\.6 Sol, 647 evaluations/);
  assert.match(copy, /41\.6% reach the global optimum/);
  assert.match(copy, /56\.3% end in a feasible but suboptimal decision/);
  assert.match(copy, /paragraph:\s*$/m);
  assert.doesNotMatch(copy, /5,040|3,876|720 evaluations/i);
  assert.doesNotMatch(copy, /Complete evidence|complete-evidence/i);
  assert.doesNotMatch(copy, /Table [123]|from the paper|Figure 1\./i);
  assert.doesNotMatch(copy, /[\u3400-\u9fff]/u);
  assert.match(abstract, /copy\.paragraph/);
  await assert.rejects(access(new URL("../src/pages/zh/index.astro", import.meta.url)));
});

test("the page preserves the editorial grid while adding restrained visual modules", async () => {
  const layout = await read("src/layouts/BaseLayout.astro");
  const styles = await read("src/styles/global.css");

  assert.match(styles, /--outer-width: 1088px/);
  assert.match(styles, /--reading-width: 1088px/);
  assert.match(styles, /--panel-shadow:/);
  assert.doesNotMatch(styles, /\.hero-fact-strip/);
  assert.match(styles, /\.validation-grid/);
  assert.match(styles, /outline: 3px solid #0b676c/);
  assert.match(styles, /grid-template-columns: repeat\(auto-fit, minmax\(150px, 1fr\)\)/);
  assert.match(styles, /flex: var\(--count\) 0 0/);
  assert.doesNotMatch(styles, /brands\/providers/);
  assert.match(layout, /IntersectionObserver/);
  assert.match(layout, /prefers-reduced-motion: reduce/);
  assert.doesNotMatch(styles, /@keyframes/);
});

test("the site uses only Weixin AI identity and no individual author names", async () => {
  const sources = await Promise.all([
    read("src/data/site.ts"),
    read("src/components/Masthead.astro"),
    read("src/components/SiteHeader.astro"),
    read("src/components/SiteFooter.astro"),
    read("src/layouts/BaseLayout.astro"),
    read("public/brands/weixin-mark.svg"),
  ]);
  const combined = sources.join("\n");

  assert.match(combined, /Weixin AI/);
  assert.match(combined, /weixin-mark\.svg/);
  assert.doesNotMatch(combined, new RegExp(`We${"Chat"} AI`, "i"));
  const individualNames = [
    ["Zi", "xiang", " Xu"],
    ["Ji", "aan", " Wang"],
    ["Fan", "dong", " Meng"],
  ].map((parts) => parts.join(""));
  for (const name of individualNames) assert.doesNotMatch(combined, new RegExp(name));
  assert.doesNotMatch(combined, new RegExp(["University of Southern", " California"].join("")));
});

test("release-reviewed website assets stay out of the static output", async () => {
  const inventory = JSON.parse(await read("docs/assets/ASSETS.json"));
  /** @type {Array<{ path: string; sha256: string; kind: string; redistribution_status: string; release_blocker: boolean }>} */
  const inventoryAssets = inventory.assets;
  const brandNotes = await read("docs/assets/brands.md");
  const figureNotes = await read("docs/assets/figures.md");
  const publicBrands = await readdir(new URL("../public/brands/", import.meta.url));
  const publicFigures = await readdir(new URL("../public/figures/", import.meta.url));

  assert.equal(inventory.release_approved, true);
  assert.deepEqual(inventory.release_blockers, []);
  assert.equal(inventory.release_approval.approved_by, "AlgoWorlds project lead");
  assert.equal(inventory.release_approval.approved_on, "2026-08-28");
  assert.equal(inventoryAssets.every((asset) => asset.redistribution_status === "approved"), true);
  assert.equal(inventoryAssets.every((asset) => asset.release_blocker === false), true);
  assert.equal(inventoryAssets.some((asset) => asset.kind === "provider_trademark"), false);
  for (const asset of inventoryAssets) {
    assert.equal(sha256(await readBytes(asset.path)), asset.sha256, asset.path);
  }
  assert.deepEqual(publicBrands, ["weixin-mark.svg"]);
  assert.deepEqual(publicFigures, ["algoworlds-figure-1.png"]);
  assert.match(brandNotes, /neutral text badges/);
  assert.match(figureNotes, /2026-08-28/);
  await assert.rejects(access(new URL("../public/ASSETS.json", import.meta.url)));
});

test("the project visualization matches the latest source without exposing a PDF", async () => {
  const figure = await readBytes("public/figures/algoworlds-figure-1.png");
  const copy = await read("src/content/copy.ts");
  const site = await read("src/data/site.ts");

  assert.equal(sha256(figure), "2509ed1e2815a5c39224d8487f34d7e420b1424037ebef6664625bb77f9321d8");
  assert.equal(figure.readUInt32BE(16), 2850);
  assert.equal(figure.readUInt32BE(20), 816);
  assert.match(copy, /caption:\s*"Sufficient information does not guarantee global optimality\."/);
  assert.match(copy, /alt:\s*"Exact-optimality rates for seven evaluated LLMs;[^\n]+information sufficiency/i);
  assert.match(site, /width: 2850/);
  assert.match(site, /height: 816/);
  await assert.rejects(access(new URL("../public/paper.pdf", import.meta.url)));
});

test("the web tables mirror the three current paper tables", async () => {
  const copy = await read("src/content/copy.ts");
  const site = await read("src/data/site.ts");
  const benchmark = await read("src/components/BenchmarkArticle.astro");
  const results = await read("src/components/ResultsArticle.astro");

  for (const family of [
    "Transit Routing",
    "Basket Assembly",
    "Station Siting",
    "Authorization Planning",
    "Series Portfolio",
    "Machine Layout",
    "Sequential Matching",
    "Fleet Dispatch",
    "Evidence-Joined Routing",
    "Migration Portfolio",
  ]) assert.match(site, new RegExp(family));
  assert.match(copy, /Aspect/);
  assert.match(copy, /measures: "Metric"/);
  assert.match(copy, /diagnosticQuestion: "Definition"/);
  assert.match(benchmark, /definition\.instanceData/);
  assert.match(benchmark, /definition\.method/);
  assert.match(results, /rankedModels = \[\.\.\.results\.models\]\.sort/);
  assert.match(results, /right\.exact\.mean - left\.exact\.mean/);
  assert.match(results, /results\.informationSufficiencyDiagnostic/);
  assert.doesNotMatch(results, /results\.panelInformationSufficiencyDiagnostic/);
  assert.match(results, /filter\(\(outcome\) => outcome\.count > 0\)/);
  assert.match(results, /style={`--count: \$\{outcome\.count\}`}/);
  assert.match(results, /aria-sort="descending"/);
  assert.match(results, /copy\.finalDecisionGroup/);
  assert.match(results, /copy\.trajectoryGroup/);
});

test("semantic labels and definition lists preserve the established visual order", async () => {
  const benchmark = await read("src/components/BenchmarkArticle.astro");
  const figure = await read("src/components/PaperFigure.astro");
  const footer = await read("src/components/SiteFooter.astro");
  const site = await read("src/data/site.ts");

  assert.match(benchmark, /<dt>{fact\.label}<\/dt>\s*<dd>{fact\.value}<\/dd>/);
  assert.match(benchmark, /<dt>{fact\.label}<\/dt>\s*<dd>{fact\.value}<\/dd>/g);
  assert.match(benchmark, /<section class="table-region" tabindex="0" aria-label=/);
  assert.match(figure, /<section class="paper-figure-viewport" tabindex="0" aria-label=/);
  assert.match(figure, /<figcaption>[\s\S]*paper-figure-hint[\s\S]*<\/figcaption>/);
  assert.match(footer, /aria-label="Footer project resources"/);
  assert.match(site, /title: "AlgoWorlds \| Weixin AI"/);
});

test("the leaderboard identifies providers without third-party image assets", async () => {
  const results = await read("src/components/ResultsArticle.astro");
  const site = await read("src/data/site.ts");

  assert.match(results, /class="provider-badge"/);
  assert.doesNotMatch(`${results}\n${site}`, /brands\/providers|anthropic\.png|openai\.png|zai\.png|deepseek\.png|qwen\.png/);
});

test("the project exposes arXiv and one combined GitHub resource", async () => {
  const masthead = await read("src/components/Masthead.astro");
  const footer = await read("src/components/SiteFooter.astro");
  const site = await read("src/data/site.ts");
  const layout = await read("src/layouts/BaseLayout.astro");
  const icon = await read("src/components/Icon.astro");

  assert.match(site, /href: "https:\/\/arxiv\.org\/abs\/2608\.29397"/);
  assert.match(site, /label: "Code & Dataset"/);
  assert.match(site, /github\.com\/xzx34\/AlgoWorlds/);
  assert.match(masthead, /siteConfig\.resources\.repository/);
  assert.match(footer, /siteConfig\.resources\.repository/);
  assert.doesNotMatch(`${site}\n${masthead}\n${footer}\n${layout}`, /paper\.pdf|paperPdf|ScholarlyArticle/);
  assert.match(icon, /"paper"/);
  assert.match(icon, /"github"/);
});

test("custom web figures remain removed in favor of the paper artwork", async () => {
  const components = await readdir(new URL("../src/components/", import.meta.url));

  assert.equal(components.includes("OverviewFigure.astro"), false);
  assert.equal(components.includes("ResultsFigure.astro"), false);
  assert.equal(components.includes("CitationSection.astro"), false);
});
