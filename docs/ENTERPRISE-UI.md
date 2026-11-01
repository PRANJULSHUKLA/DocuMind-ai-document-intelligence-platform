# DocuMind — Graphite Precision

Frontend redesign based on verified main `b10554ea3572773242807a9229b5086af7bfc7af`. The stable application on port 5179 is unchanged. This branch previews on private port 5182 and requires approval before merge.

## Design system

Inter Variable 100–900, self-hosted through `@fontsource-variable/inter` 5.3.0. The application bundles one 48.25 kB Latin WOFF2 with `font-display: swap`, plus system fallbacks for other scripts. License: SIL Open Font License 1.1, included at `frontend/public/fonts/Inter-OFL.txt`. No font CDN, external images, icon service, or additional UI framework.

| Semantic token | Dark (default) | Light |
| --- | --- | --- |
| Canvas | #0B1118 | #F7F9FB |
| Sidebar | #101820 | #EDF1F5 |
| Surface | #151E28 | #FFFFFF |
| Raised | #1C2835 | #EDF2F6 |
| Muted | #111B25 | #F4F7FA |
| Border | #2A3542 | #DBE2EA |
| Input border | #526377 | #748398 |
| Primary text | #F4F7FA | #17212B |
| Secondary text | #A4B0BE | #526174 |
| Accent | #2DD4BF | #08756B |
| Accent hover | #5EE4D2 | #065E56 |
| On accent | #062B29 | #FFFFFF |
| Accent surface | #143632 | #E1F3F0 |
| Success / surface | #83D9AA / #17332A | #236342 / #E6F4EB |
| Warning / surface | #F4C779 / #392D1B | #805400 / #FFF3D8 |
| Error / surface | #FFA6AC / #3B222A | #A52637 / #FFF0F1 |

Colors are CSS variables connected to Tailwind 4 semantic utilities. Status always includes text. The primary PDF remains white with black document text in both themes.

Typography: page titles 28–30 px, section titles 18–22 px, card titles 15–18 px, body 14–16 px, secondary 13–14 px, metadata 12 px. Metrics use tabular numerals. Long filenames wrap; quotations retain whitespace and wrap without overflowing. Ordinary labels use sentence case. Radii: 6 / 10 / 14 px; spacing follows a 4 px scale; focus: 2 px outline with 3 px offset; transitions 160 ms and disabled for reduced motion.

Shared primitives in `src/components/ui.jsx`: buttons, input, card, badge, status message, skeleton, keyboard-operated tabs, modal dialog, tooltip and list header. Theme preference is stored only in browser localStorage; blocked storage falls back safely. Theme changes do not remount the application or reader.

## Redesigned views

- Shell: product identity, grouped desktop sidebar, two-row mobile navigation, current-document context, theme control, skip link and workspace information dialog.
- Dashboard: verified data counts, recent documents, clear upload/open actions, collection entry, evidence guidance.
- Documents: filename, type, page count, textual processing badge, upload selection and drag-and-drop, stage feedback and original retry safeguards.
- Read & Ask: balanced PDF/chat split, PDF controls, mobile tabs, extracted-text search, exact evidence inspection, version warnings and source navigation.
- Assistant: distinct messages, readable text and source cards, suggestions, composer, processing and provider errors. No unsafe HTML/Markdown rendering added.
- Collections: separate creation/selection, membership and question context, adjacent comparison/chat workspaces, independent upload statuses.
- Comparison: explicit bounded-mode choice, selected documents, structured facts, classification counts, evidence and uncertainty, reviewed-report form.
- Reports: list/detail, stale-source warning, JSON/PDF download state, evidence links, explicit native delete confirmation.
- Intelligence and workflow: matching surfaces, severity and readiness colors, readable evidence, parties/obligations/deadlines/actions and approval notices.
- Authentication: matching surfaces while retaining existing OIDC/dev-mode boundaries.

## Trust and state behavior

Library loading and failure show unknown counts (`—`), never verified zero. Empty-state copy appears only after a successful empty list. Failed refresh retains prior rows, labels counts unavailable and warns that rows may be stale. Authentication failures have distinct text. Safe Retry only reloads the list. Collection and report lists distinguish initial loading/failure from empty results. Search does not claim no matches before a successful search response.

Theme and reading-panel changes retain PDF page, zoom, chat history, unsent draft and selected evidence. Search input also survives main navigation. PDF.js remains lazy-loaded. Existing upload acceptance/recovery behavior, source version checks, report validation and API contracts are unchanged.

Comparison remains bounded rule-based normalization of supported facts and explicit obligations. It does not establish unrestricted semantic equivalence, full-document completeness or verified legacy provenance. No provider calls are made by export.

## Reproduce locally

Inside the existing Dev Container, with the stable local backend already running on loopback port 8000:

```bash
cd /workspaces/full-rag/.worktrees/enterprise-ui-redesign/frontend
npm ci
CHOKIDAR_USEPOLLING=true VITE_AUTH_MODE=development VITE_API_BASE_URL=/api npm run dev -- --host 127.0.0.1 --port 5182 --strictPort --force
```

Forward port 5182 privately in VS Code and open http://127.0.0.1:5182/. Do not change the stable frontend's port or publicly forward development authentication. No second backend or worker is needed. File polling helps edits propagate through Docker Desktop's bind mount.

```bash
# Worktree root
python -m pytest -q
# frontend/
npm test
npm run lint
npm run build
npm run test:browser
```

All browser scenarios intercept API requests with synthetic fixtures. They make no paid model calls and create no Atlas records. Axe is development-only and does not enter the product bundle. Automated accessibility checks complement, rather than certify, WCAG conformance; manual screen-reader and real managed-OIDC testing remain future work.

## Review evidence

The browser suite captures dark/light dashboard, library, reader, intelligence, workflow and collection/report screens at 360, 768, 1280 and 1440 px. It asserts no document-level horizontal overflow, verifies local font loading, theme persistence, reading state, keyboard tabs, reduced motion, dialog focus, error states and provider quota handling. Existing six scenarios still verify citation navigation, collection chat, comparison and report JSON/PDF export.

Selected real before/after screenshots use synthetic documents only. The before images were captured on stable main; their stored provenance is described alongside the images. Fixture counts are test data, never product analytics. Full browser captures are available in the GitHub CI `browser-evidence` artifact.

## Preserved boundaries and limitations

No backend, OCR, embedding, retrieval, worker, model retry/fallback, storage, Atlas or authentication configuration changes. No document creation, reprocessing, ownership migration or deletion was performed against the live application. Existing historical records and local agent edits are outside this branch. The original 5179 application remains available.

Known nonblocking build warning: PDF.js stays in its existing large, lazy-loaded chunk. The redesign does not add rich Markdown rendering or resizable pane state. Collections can still be long on mobile; membership, evidence and reports are explicitly separated into sections. Native delete confirmation preserves cancellation and keyboard behavior. Managed OIDC, broader live model evaluation and production operations remain outside scope.

## Verified results

- Complete backend regression suite: **200 passed**, two existing deprecation warnings.
- Frontend unit tests: **27 passed**, including theme persistence/blocked storage, loading vs failure vs empty, retained stale rows, authentication errors and upload drag/drop/retry recovery.
- Lint and production build: **passed**. Main JS: 351.76 kB (107.88 kB gzip); local font: 48.25 kB; existing lazy PDF chunk: 633.46 kB.
- Chromium: **23 passed**, including the original six scenarios, eight width/theme combinations, reading-state preservation, modal/tab keyboard behavior, reduced motion, missing originals/legacy provenance, provider 429 no-auto-retry and automated WCAG-tagged checks of both themes.
- Axe: no violations in the exercised desktop dashboard, upload/library, reader, intelligence, workflow, bounded comparison/facts and report views, plus mobile collections/reports. Automated checks do not replace assistive-technology review.
- Live private preview: existing workspace document list and original two-page PDF verified; no model request, reprocessing or data mutation required.

See [before/after review captures](ui-review/README.md). Provider responses in integration/browser tests are synthetic, not evidence of newly tested live Gemini/OIDC behavior.
