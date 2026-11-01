import { test, expect } from "@playwright/test";
import fs from "node:fs";
import crypto from "node:crypto";

const id = "507f1f77bcf86cd799439011",
  other = "507f1f77bcf86cd799439012";
const pdf = fs.readFileSync(
  new URL("./fixtures/synthetic.pdf", import.meta.url),
);
const hash = crypto.createHash("sha256").update(pdf).digest("hex");
const filename = "Northstar supplier agreement — 2026.pdf";
const source = {
  file_id: id,
  filename,
  evidence_id: "e1",
  source_id: "s1",
  page_number: 2,
  chunk_index: 1,
  processing_run_id: "run-1",
  content_sha256: hash,
  excerpt: "Payment USD 100 due December 1, 2026.",
};
const snapshot = {
  method: "literal_plus_verified_normalization_v1",
  review_digest: "a".repeat(64),
  summary: { supported_difference: 1, insufficient_evidence: 1 },
  limitations: [
    "Bounded rule-based normalization; no unrestricted semantic understanding or full-document completeness.",
  ],
  extracted_facts: [
    {
      fact_id: "f1",
      kind: "amount",
      value: { currency: "USD", amount: "100" },
      quotation: source.excerpt,
      uncertainty: "explicit",
      source,
    },
  ],
  sources: [source],
  findings: [
    {
      topic: "Payment amount",
      classification: "supported_difference",
      explanation:
        "Explicit amounts differ in the retrieved evidence. This does not establish a contractual contradiction.",
      documents: [
        {
          file_id: id,
          filename,
          facts: [{ values: ["USD 100"], evidence_id: "e1" }],
        },
        { file_id: other, filename: "Northstar renewal.pdf", facts: [] },
      ],
    },
    {
      topic: "Conditional delivery obligation",
      classification: "insufficient_evidence",
      explanation:
        "The conditional clause falls outside the supported grammar. Human review is required.",
      documents: [],
    },
  ],
};

async function fixtures(page, { filesError = false } = {}) {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/files")
      return route.fulfill(
        filesError
          ? {
              status: 503,
              json: { detail: "Database temporarily unavailable" },
            }
          : {
              json: [
                { _id: id, filename, total_pages: 2, status: "completed" },
                {
                  _id: other,
                  filename: "Northstar renewal.pdf",
                  status: "completed",
                },
                {
                  _id: "queued",
                  filename: "Delivery terms.pdf",
                  status: "processing",
                },
                {
                  _id: "failed",
                  filename: "Scanned appendix.pdf",
                  status: "failed",
                },
              ],
            },
      );
    if (path.endsWith("/content"))
      return route.fulfill({ contentType: "application/pdf", body: pdf });
    if (path.endsWith("/view"))
      return route.fulfill({
        json: {
          file_id: id,
          filename,
          status: "completed",
          version: "v1",
          total_pages: 2,
          processing_run_id: "run-1",
          content_sha256: hash,
          original_available: true,
          provenance: "verified",
        },
      });
    if (path.endsWith("/search"))
      return route.fulfill({ json: { results: [source] } });
    if (path.endsWith("/chat") || path === "/api/chat")
      return route.fulfill({
        json: {
          answer:
            "The retrieved passage states USD 100 due December 1, 2026. Review the original clause before relying on it.",
          sources: [source],
          total_time_ms: 2,
        },
      });
    if (path === "/api/collections")
      return route.fulfill({
        json: [
          {
            id: "contracts",
            name: "Supplier review",
            file_ids: [id, other],
            revision: 1,
          },
        ],
      });
    if (path.endsWith("/compare-semantic"))
      return route.fulfill({ json: snapshot });
    if (path === "/api/comparison-reports")
      return route.fulfill({
        json: [{ id: "report1", title: "Supplier payment review" }],
      });
    if (path === "/api/comparison-reports/report1")
      return route.fulfill({
        json: {
          id: "report1",
          title: "Supplier payment review",
          created_at: "2026-11-01",
          stale: true,
          snapshot,
        },
      });
    if (path === "/api/analyze")
      return route.fulfill({
        json: {
          analysis: {
            document_type: "Supplier agreement",
            executive_summary:
              "Synthetic supplier terms include an explicit payment amount and delivery obligations. Review the incomplete termination clause before approval.",
            risks: [
              {
                title: "Incomplete termination terms",
                severity: "high",
                category: "Contract",
                explanation:
                  "The available passage does not define notice requirements.",
                evidence: "Termination requires notice.",
              },
            ],
            parties: [
              { name: "Northstar", role: "Buyer" },
              { name: "Example Supply", role: "Supplier" },
            ],
            obligations: [
              {
                party: "Buyer",
                obligation: "Pay USD 100 by the stated date.",
                deadline: "December 1, 2026",
                evidence: source.excerpt,
              },
            ],
            key_terms: ["Payment", "Delivery"],
            missing_information: [
              {
                item: "Notice period",
                reason: "Not specified in the retrieved passage.",
              },
            ],
          },
        },
      });
    if (path === "/api/workflow")
      return route.fulfill({
        json: {
          workflow: {
            readiness_status: "conditionally_ready",
            overall_assessment: "Review the incomplete terms before approval.",
            human_approval_required: true,
            approval_reason: "Contract owner must confirm notice requirements.",
            immediate_actions: [
              {
                title: "Confirm notice requirements",
                priority: "high",
                action:
                  "Ask the contract owner to review the termination clause.",
                reason: "Required notice is not specified.",
                evidence: "Termination requires notice.",
                requires_human_approval: true,
              },
            ],
            upcoming_actions: [],
            monitoring_items: [],
          },
        },
      });
    failures.push(`Unexpected fixture request: ${path}`);
    return route.fulfill({
      status: 501,
      json: { detail: "Unexpected test request" },
    });
  });
  return failures;
}
async function noOverflow(page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
}
async function shot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `test-results/redesign/${name}.png`,
    fullPage: true,
    animations: "disabled",
  });
}
for (const theme of ["dark", "light"])
  for (const width of [360, 768, 1280, 1440]) {
    test(`${theme} responsive application at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      await page.addInitScript(
        (value) => localStorage.setItem("documind-theme", value),
        theme,
      );
      const failures = await fixtures(page);
      await page.goto("/");
      await expect(page.getByLabel("Total documents: 4")).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      expect(
        await page.evaluate(() =>
          document.fonts.check('14px "Inter Variable"'),
        ),
      ).toBe(true);
      await noOverflow(page);
      await shot(page, `${theme}-${width}-dashboard`);
      await page
        .getByRole("button", { name: "Documents", exact: true })
        .first()
        .click();
      await noOverflow(page);
      await shot(page, `${theme}-${width}-documents`);
      await page
        .getByRole("button", { name: new RegExp(filename) })
        .first()
        .click();
      await expect(page.locator("canvas").first()).toBeVisible();
      await noOverflow(page);
      await shot(page, `${theme}-${width}-reader`);
      await page
        .getByRole("button", { name: "Intelligence", exact: true })
        .first()
        .click();
      await page
        .getByRole("button", { name: "Run Document Intelligence" })
        .click();
      await expect(
        page.getByText("Executive summary", { exact: true }),
      ).toBeVisible();
      await noOverflow(page);
      await shot(page, `${theme}-${width}-intelligence`);
      await page
        .getByRole("button", {
          name: width >= 1024 ? "Action Workflow" : "Workflow",
          exact: true,
        })
        .first()
        .click();
      await page.getByRole("button", { name: "Generate action plan" }).click();
      await expect(
        page.getByText("Confirm notice requirements", { exact: true }),
      ).toBeVisible();
      await noOverflow(page);
      await shot(page, `${theme}-${width}-workflow`);
      await page
        .getByRole("button", { name: "Collections", exact: true })
        .first()
        .click();
      await page.getByLabel("Active collection").selectOption("contracts");
      const comparison = page.getByRole("region", {
        name: "Document comparison",
      });
      await comparison
        .getByLabel("Use validated obligation comparison (bounded)")
        .check();
      await comparison.getByLabel(`${filename} · completed`).check();
      await comparison.getByLabel("Northstar renewal.pdf · completed").check();
      await comparison
        .getByRole("button", { name: "Compare selected documents" })
        .click();
      await expect(
        comparison.getByText("Supported difference", { exact: true }),
      ).toBeVisible();
      await comparison
        .getByText("Review structured evidence facts (1)")
        .click();
      const reports = page.getByRole("region", {
        name: "Saved comparison reports",
      });
      await reports
        .getByRole("button", { name: "Open report: Supplier payment review" })
        .click();
      await expect(reports.getByText(/STALE:/)).toBeVisible();
      await noOverflow(page);
      await shot(page, `${theme}-${width}-collections`);
      expect(failures).toEqual([]);
    });
  }
for (const width of [360, 1440])
  test(`theme and panel switching retain reading state at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await fixtures(page);
    await page.goto("/");
    await page
      .getByRole("button", { name: new RegExp(filename) })
      .first()
      .click();
    await expect(page.locator("canvas").first()).toBeVisible();
    await page.getByRole("button", { name: "Next page" }).click();
    await page.getByRole("button", { name: "Zoom in" }).click();
    if (width < 1024)
      await page.getByRole("tab", { name: "chat", exact: true }).click();
    await page.getByLabel("Ask a question").fill("What is the payment?");
    await page.getByRole("button", { name: "Ask document" }).click();
    await page.getByRole("button", { name: `Open ${filename} page 2` }).click();
    if (width < 1024)
      await page.getByRole("tab", { name: "chat", exact: true }).click();
    await page.getByLabel("Ask a question").fill("Keep this unsent draft");
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await expect(page.getByLabel("Ask a question")).toHaveValue(
      "Keep this unsent draft",
    );
    await expect(page.getByText(/The retrieved passage states/)).toBeVisible();
    if (width < 1024) {
      await page.getByRole("tab", { name: "evidence", exact: true }).click();
      await expect(
        page.getByRole("region", { name: "Selected evidence" }),
      ).toContainText(source.excerpt);
      await page.getByRole("tab", { name: "document", exact: true }).click();
    }
    await expect(
      page.getByRole("spinbutton", { name: "Page number" }),
    ).toHaveValue("2");
    await expect(page.getByText("125%", { exact: true })).toBeVisible();
    await page.getByLabel("Search document").fill("100");
    await expect(
      page.getByRole("button", { name: /Page 2 Payment USD/ }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Dashboard", exact: true })
      .first()
      .click();
    await page
      .getByRole("button", {
        name: width >= 1024 ? "AI Assistant" : "Assistant",
        exact: true,
      })
      .first()
      .click();
    await expect(page.getByLabel("Search document")).toHaveValue("100");
    await expect(
      page.getByRole("spinbutton", { name: "Page number" }),
    ).toHaveValue("2");
    await expect(page.getByText("125%", { exact: true })).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Switch to dark mode" }),
    ).toBeVisible();
  });
test("API failure is visibly different from loading and an empty workspace", async ({
  page,
}) => {
  await fixtures(page, { filesError: true });
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Document library unavailable",
  );
  await expect(page.getByLabel("Total documents: unavailable")).toHaveText("—");
  await expect(
    page.getByText("Your workspace is ready", { exact: true }),
  ).toHaveCount(0);
  await shot(page, "error-state");
  await page
    .getByRole("button", { name: "Documents", exact: true })
    .first()
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Document library unavailable",
  );
  await expect(page.getByText("No documents yet", { exact: true })).toHaveCount(
    0,
  );
});
test("dialog traps focus, closes with Escape, and restores trigger focus", async ({
  page,
}) => {
  await fixtures(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  const trigger = page.getByRole("button", { name: "Workspace details" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Your local workspace" });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Close dialog" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Done" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
});
test("keyboard tabs support arrow navigation and reduced motion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await fixtures(page);
  await page.goto("/");
  await page
    .getByRole("button", { name: new RegExp(filename) })
    .first()
    .click();
  const tab = page.getByRole("tab", { name: "document", exact: true });
  await tab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "chat", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("tab", { name: "chat", exact: true }),
  ).toBeFocused();
  expect(
    await page.evaluate(
      () =>
        getComputedStyle(document.querySelector("button")).transitionDuration,
    ),
  ).toBe("0s");
});

for (const theme of ["dark", "light"])
  test(`WCAG checks on key ${theme} views`, async ({ page }) => {
    test.setTimeout(60000);
    const { default: AxeBuilder } = await import("@axe-core/playwright");
    await page.addInitScript(
      (value) => localStorage.setItem("documind-theme", value),
      theme,
    );
    await page.setViewportSize({ width: 1280, height: 1000 });
    await fixtures(page);
    async function audit(label) {
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(
        result.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            summary: n.failureSummary,
          })),
        })),
        label,
      ).toEqual([]);
    }
    await page.goto("/");
    await expect(page.getByLabel("Total documents: 4")).toBeVisible();
    await audit("dashboard");
    await page
      .getByRole("button", { name: "Documents", exact: true })
      .first()
      .click();
    await audit("documents and upload");
    await page
      .getByRole("button", { name: new RegExp(filename) })
      .first()
      .click();
    await expect(page.locator("canvas").first()).toBeVisible();
    await audit("reader");
    await page
      .getByRole("button", { name: "Intelligence", exact: true })
      .first()
      .click();
    await page
      .getByRole("button", { name: "Run Document Intelligence" })
      .click();
    await expect(
      page.getByText("Executive summary", { exact: true }),
    ).toBeVisible();
    await audit("intelligence");
    await page
      .getByRole("button", { name: "Action Workflow", exact: true })
      .first()
      .click();
    await page.getByRole("button", { name: "Generate action plan" }).click();
    await expect(
      page.getByText("Confirm notice requirements", { exact: true }),
    ).toBeVisible();
    await audit("workflow");
    await page
      .getByRole("button", { name: "Collections", exact: true })
      .first()
      .click();
    await page.getByLabel("Active collection").selectOption("contracts");
    const comparison = page.getByRole("region", {
      name: "Document comparison",
    });
    await comparison
      .getByLabel("Use validated obligation comparison (bounded)")
      .check();
    await comparison.getByLabel(`${filename} · completed`).check();
    await comparison.getByLabel("Northstar renewal.pdf · completed").check();
    await comparison
      .getByRole("button", { name: "Compare selected documents" })
      .click();
    await expect(
      comparison.getByText("Supported difference", { exact: true }),
    ).toBeVisible();
    await comparison.getByText("Review structured evidence facts (1)").click();
    await page
      .getByRole("button", { name: "Open report: Supplier payment review" })
      .click();
    await audit("collections and reports");
    await page.setViewportSize({ width: 360, height: 900 });
    await audit("mobile collections and reports");
  });

test("missing originals and legacy provenance remain explicit", async ({
  page,
}) => {
  await fixtures(page);
  await page.route("**/api/files/*/view", (route) =>
    route.fulfill({
      json: {
        file_id: id,
        filename,
        status: "completed",
        version: "legacy",
        total_pages: 2,
        original_available: false,
        provenance: "legacy_unverified",
      },
    }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: new RegExp(filename) })
    .first()
    .click();
  await expect(
    page.getByText(
      /Original PDF is unavailable. Existing analysis is retained./,
    ),
  ).toBeVisible();
  await expect(
    page.getByText(/historical OCR bytes are not cryptographically verified/),
  ).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
});
test("provider quota failure is visible and never automatically retried", async ({
  page,
}) => {
  await fixtures(page);
  let requests = 0;
  await page.route("**/api/chat", (route) => {
    requests++;
    return route.fulfill({
      status: 429,
      json: { detail: "Model quota exhausted. Try again later." },
    });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: new RegExp(filename) })
    .first()
    .click();
  await page.getByLabel("Ask a question").fill("What amount is due?");
  await page.getByRole("button", { name: "Ask document" }).click();
  await expect(page.getByRole("alert")).toContainText("Model quota exhausted");
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(page.getByRole("alert")).toContainText("Model quota exhausted");
  expect(requests).toBe(1);
});
