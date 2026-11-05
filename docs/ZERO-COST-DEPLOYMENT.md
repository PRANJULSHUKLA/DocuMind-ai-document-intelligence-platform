# DocuMind zero-cost deployment preflight

Checked 5 November 2026. Stable main is `b10554ea3572773242807a9229b5086af7bfc7af`. Dedicated branch: `codex/zero-cost-deployment`. UI PR #13 remains separate and unmerged. No running development checkout, credentials, upload, database record, Atlas index or Docker volume was modified by these preparations.

**Status: STATIC DEMO published at https://documind-ai-showcase.pages.dev/.** Cloudflare Free account verified; one static Pages Direct Upload project is live. The real backend is not deployed: the operator has no Oracle account, and the managed-identity/budget/persistence gates below remain incomplete. This is not a private-beta or production-readiness certification.

## Actual account preflight

| Service | Observed account state | What remains unverified |
| --- | --- | --- |
| Cloudflare | Signed in; current Workers plan Free ($0), no existing projects and zero requests at preflight. Static Pages project successfully published. | Recheck eligibility before any future paid feature or infrastructure change; no such change was made. |
| Oracle | Operator confirmed no Oracle account | Account creation/eligibility, tenancy/home region, current free allocations, A1 capacity, boot/data volumes, IP/egress and billing status |
| Atlas | Old tab displayed cached network settings; fresh reload required login | Current tier, storage/use, vector index compatibility, backup eligibility, deployment-source access and TLS from a real VM |
| Gemini | No model request made | Project billing disabled, exact model availability and per-project free RPM/TPM/RPD, bounded usage reservation |
| Managed OIDC | No configured production tenant/application available in this handoff | Free account eligibility, issuer/audience, PKCE, exact callbacks and two real test identities |

The operator signed in directly to Cloudflare and confirmed there is no Oracle account. No password, card, API key or SSH private key was requested in chat. Atlas must also be signed in again before its current account state can be inspected. No account was upgraded or signup agreement accepted.

## Provider documentation, not account-level eligibility

- [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm): current Always Free A1 allowance is 1,500 OCPU-hours and 9,000 GB-hours monthly, equivalent to 2 OCPUs/12 GB. Resources must be in the home region; idle compute may be reclaimed and free shape capacity may be unavailable. Combined boot/block storage allowance is 200 GB, with five volume backups. Actual existing allocations must be counted before choosing sizes. Do not use the older 4 OCPU/24 GB assumption. [Free-tier billing](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm) distinguishes Always Free from expiring promotional resources; do not upgrade to PAYG.
- [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/): Free lists 500 builds/month, one concurrent build, 20,000 files and 25 MiB per asset. [Static asset requests](https://developers.cloudflare.com/pages/functions/pricing/) are free/unlimited when Functions are not invoked. This showcase has no Functions, Workers, R2, database or model integration. No paid domain is required for a provider-assigned `pages.dev` address.
- [Atlas Free limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/): 0.5 GB data/index storage. Current documentation describes optional daily backups retaining four snapshots; availability and zero-cost eligibility must be checked in this account before enabling anything. Do not assume existing backup coverage. Vector index type, embedding dimensions and namespace must be verified without changing live indexes.
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) lists free usage for eligible models, including standard `gemini-embedding-001`; [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) are project-specific and do not guarantee available quota. [Billing](https://ai.google.dev/gemini-api/docs/billing/) must remain Free, with no linked paid usage or automatic overages. Free-tier data-use terms also require review before sensitive documents can be approved. Exact generation/OCR models are intentionally blank in the template; no `latest` alias is accepted.
- [Auth0 Free pricing](https://auth0.com/pricing) currently advertises up to 25,000 monthly active users and social connections. This is only a candidate, not a selected/configured provider. A provider-issued RS256 JWT API access token, correct audience and issuer, and real workspace-isolation tests are required. Do not infer compatibility from a pricing card alone or enable a trial/paid/custom-domain feature.

There is no unconditional promise that a provider will keep these offers forever. A ₹0 claim requires the actual selected resources, account terms, existing consumption and proposed usage to pass the live checks.

## Prepared private staging configuration

`deploy/production/Dockerfile` uses the exact verified multi-platform Python image index digest. Python and Valkey manifest indexes both advertise Linux Arm64. Python dependencies remain the existing pinned `requirements.txt`; Poppler supplies PDF rendering. The build only copies application code and the two deployment scripts, runs as UID 10001, and excludes local files/secrets via an allowlist `.dockerignore`. Debian package repositories remain moving security repositories, so this is not a bit-for-bit hermetic OS build.

`compose.yaml` is deliberately **private staging only**:

- API binds host `127.0.0.1:18000`, one Uvicorn process, concurrency 8, no reload and no trusted forwarded-header authentication bypass.
- Valkey exposes no host port, persists its AOF, uses 128 MB maxmemory/noeviction, and is dedicated to this new project. No public Redis or database administration endpoint.
- One worker is available only with explicit `--profile processing`; it does not start by default. Never start it until billing/quota and synthetic-job approval are recorded.
- API and worker share a new private originals volume. The project is named `documind-staging`, not the existing Dev Container project. No existing volume is reused.
- Resource ceilings: API 0.75 CPU/1 GB, worker 1 CPU/2 GB, queue 0.25 CPU/256 MB. These are container ceilings, not a proven throughput claim or approved VM allocation.
- Read-only application root, temporary scratch space, dropped capabilities, bounded log rotation and restart policy.
- Production/OIDC-only entry guard, HTTPS origins, Atlas SRV certificate validation, absolute upload path, 5 MB uploads. By deployment configuration only, model automatic retries are zero and fallbacks empty; existing Gemini source/retry integration is unchanged.
- Read-only health probe checks upload-directory access, Redis PING and MongoDB PING with ordinary TLS. It makes no model call, query of document records, write or index change.

`Caddyfile.blocked` is intentionally a 503 response, not a working public API. A verified hostname/DNS/certificate path is still required. No free dynamic DNS, free fixed-IP product, public certificate or image-host compatibility is assumed. Do not switch to a forwarding Caddy configuration until the following release gates pass.

## Essential remaining security gates

1. Establish an approved private-pilot identity allowlist; configure managed OIDC SPA PKCE and API audience. Verify issuer, audience, signature, expiry, both users and cross-workspace denial using real identities. Disable public signup/access outside the approved pilot.
2. Implement and test per-user/global request and upload limits, durable model budgets across API and worker, finite page/chunk limits and bounded queue admission. Current stable main has a byte limit but no complete per-user quota system or ingestion page ceiling. Container concurrency is not a substitute for those limits.
3. Verify model free quotas and a finite synthetic test budget before any OCR/embedding/question. Do not automatically retry quota exhaustion or use an unverified fallback. The staging environment removes configured retries but does not itself implement full usage accounting.
4. Verify Atlas TLS/vector search from the actual VM, with a narrowly scoped deployment source entry only after specific security approval. Do not widen the existing allowlist or change existing records/indexes. A separate pilot namespace/database and its own reviewed indexes/user will need explicit setup; the template must not be pointed at historical data for tests.
5. Provision genuinely free durable private storage only after counting all tenancy allocations. API and worker must resolve the same originals. Verify write, restart and restore using only identified synthetic files; no originals are migrated from development.
6. Set exact HTTPS frontend origin/callback/logout/API URLs; keep CORS narrow. Verify frontend bundle contains no secrets or localhost URLs. Production Vite builds must never use development auth.
7. Verify backup/restore and retention/deletion behavior, health/readiness and basic monitoring. Saved report snapshots can retain passages after a source/collection is removed; access loss withholds content but is not physical deletion. Define a retention policy before real users.

Any failure keeps processing private/closed. No claim of public readiness, live ingestion, successful OIDC or restart persistence is made by the offline tests.

## Static Cloudflare deployment — completed

`deploy/showcase/` is an independent static portfolio site. It has no login, upload form, app build, model endpoint, JavaScript, cookies, analytics, Functions or API connection. CSP blocks connections/forms and framing; Cloudflare `_headers` adds the security policy. Screenshots and quoted examples are synthetic and explicitly labeled. A screenshot of draft PR #13 is identified as a design preview rather than silently incorporating unmerged UI code.

Prefer [Pages Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/) on a verified Free account. Upload **only `deploy/showcase/`**, not the repository, `.env`, uploads, source checkout or local ZIP. Keep automatic Git production and preview builds disabled by using Direct Upload. No GitHub credential grant is needed. With Git integration instead, use only this reviewed deployment branch, turn off automatic production deployments and disable previews for all other branches; verify [branch controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/) in the account before upload. An unrelated push to main must not publish the application.

The six-file directory is below the published limits and was successfully uploaded through the Pages Direct Upload UI on the verified Free account. **Public URL: https://documind-ai-showcase.pages.dev/**. Immutable deployment alias: https://9a290f9b.documind-ai-showcase.pages.dev/. Deployment ID: `9a290f9b-6b38-47e1-9f92-eb0c8405f0a5`. Source assets match commit `0d83fcc02916a2a4fce6e566eb6eb8988613fec8`. Settings show no Git repository connected, no variables/secrets and no bindings. The default production-branch label is `main`, but there is no Git integration or webhook; an unrelated GitHub push cannot publish this project. No paid plan, domain, Function, storage binding or automatic overage was enabled.

Local preview (independent of ports 5179/5182):

```bash
cd /workspaces/full-rag/.worktrees/zero-cost-deployment
python -m http.server 5184 --bind 127.0.0.1 --directory deploy/showcase
```

## Staging start/restart/rollback — after gates, on the approved VM only

No command below provisions a VM, modifies Atlas, transfers development data or certifies a free allowance. Do not run the staging stack on the existing Dev Container.

1. Use one verified Always Free Arm64 VM only if free capacity exists, with reviewed allocation within remaining tenancy allowances. Suggested sizing for review: 2 OCPU/12 GB, 50 GB boot plus 50 GB private data, subject to actual limits and availability. Do not create a paid alternative, load balancer, NAT gateway or paid fixed-IP product. Keep inbound application ports closed; restrict SSH to the operator's approved source.
2. Put the private server environment outside Git, mode 0600. Replace all examples with verified settings. Use a separate approved pilot database/user; do not reuse local user records or create indexes without review. Mount the new persistent data location before creating the staging volumes so they cannot silently land on ephemeral root storage.
3. Pin `DOCUMIND_REVISION` to the reviewed deployment commit, and `DOCUMIND_ENV_FILE` to the private absolute env path. Validate configuration without printing resolved secrets:

```bash
docker compose -f deploy/production/compose.yaml config --quiet
docker compose -f deploy/production/compose.yaml build api
docker compose -f deploy/production/compose.yaml up -d queue api
```

4. Check `docker compose ... ps`, the read-only health probe and OIDC rejection before opening any ingress. Reach loopback via a private SSH tunnel first. Start exactly one worker with `--profile processing up -d worker` only for a preapproved bounded synthetic ingestion test.
5. Restart with `docker compose -f deploy/production/compose.yaml restart api`; restart worker only when idle. Neither restart deletes volumes. **Never use `down -v`, volume prune or cleanup scripts against development data.**
6. Roll back: stop admission/worker after the current job, check out the previous reviewed deployment commit in the server release directory, select its exact image revision, and recreate API/worker without deleting volumes. No schema migration is included. Verify originals, source versions and queue state before restoring access.

## Backup and recovery

A backup is not verified until restored in isolation. Plan a consistent set of originals, matching metadata/chunks/reports and queue publication state. Stop new writes, let active work finish, then take the approved free-volume snapshot and an encrypted pilot-only metadata dump. Keep copies independent of the VM so idle reclamation cannot destroy the only copy. Count backups and storage against verified free allowances; avoid automatic policies that silently exceed five Oracle snapshots or object storage quotas. Never export development/customer records as part of this pilot.

Restore only into an isolated approved pilot namespace/location first. Match file IDs, processing-run IDs, content hashes, counts and PDF availability. Do not reassign or claim recovery of the 54 historical unassigned records/282 chunks. No backup, restore, deletion or original migration was performed in this preflight.

## Verification record

- Remote main confirmed at the reviewed stable SHA; PR #13 head remains `b48bb58689426e797b1390a7539fde0a35f4969c`.
- Complete backend suite plus new deployment checks: **221 passed**, two existing deprecation warnings. Tests cover production-only guard, TLS/CORS/retry configuration rejection, private queue and worker opt-in, shared storage declaration, and a static showcase with no data-collection surface.
- Compose schema validated without resolving a secret file or starting any service.
- Arm64 Python/Valkey image manifest compatibility verified. Local image build and browser smoke results are recorded in the handoff once complete.
- **Not yet tested for the real backend:** Oracle provisioning, backend DNS/HTTPS, OIDC identities, budgets, Atlas/vector search from VM, PDF persistence/restart/restore, live OCR/embedding/RAG/comparison/report workflows. No paid model call was made.

The static fallback is complete. Resume the real backend only with an eligible no-cost backend account/host and the required identity, quota, storage and recovery gates. Oracle remains unavailable because there is no account. Do not publish the functional frontend against localhost, a fake API, or an unverified backend.

Static browser checks: **9 passed** (the original six application scenarios plus showcase at 360/768/1440 px). Frontend lint passed. See [desktop showcase capture](deployment-review/showcase-desktop.png) and [mobile showcase capture](deployment-review/showcase-mobile.png); these are actual browser screenshots, not a deployed public site. Existing local frontend ports 5179 and 5182 both returned HTTP 200 after preparation. Original unrelated agent-edit and ZIP hashes matched the release baseline.

Local image verification completed: Linux **aarch64** image built successfully with pinned application requirements and `pip check` clean. A disposable, network-disabled read-only container imported FastAPI, MongoDB, Redis/RQ, Gemini SDK, PDF rendering and report libraries as UID **10001**, confirmed Poppler availability and no `.env` in the application image. Unconfigured startup refused to run before opening the API. No data volume or real secret was mounted. Frontend unit tests: **19 passed**; production build passed with the existing lazy PDF chunk-size warning. These local results do not establish Oracle VM capacity or successful cloud deployment.

## Public deployment verification, 5 November 2026

- Live Chromium checks at **360 and 1440 px**: HTTP 200, no page errors, no horizontal overflow, no scripts/forms/inputs, no external API requests, and zero cookies. Both screenshot assets load; the static/synthetic disclosure remains visible.
- Independent curl with ordinary certificate validation: all five served assets match the reviewed local bytes/SHA-256 hashes. Pages redirects `/404.html` to its canonical `/404` URL; the content is unchanged.
- `/api/files`, `/api/session`, `/.env` and an unknown route return **404** with the static error page, not the application or a fake backend.
- Live response headers include CSP with `connect-src 'none'`, `form-action 'none'` and `frame-ancestors 'none'`, plus nosniff, no-referrer, disabled sensitive browser permissions and DENY framing. No Set-Cookie response header.
- One client limitation: default Python urllib receives Cloudflare **403 / error 1010** while curl and real Chromium succeed. [Cloudflare documents browser-signature checks on pages.dev](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/). No security setting or certificate validation was weakened. Use a real browser or curl for this static site's health check.
- No backend URL, VM, private PDF store, OIDC tenant or model workflow was deployed. There were no model calls. This result is **STATIC DEMO**, not PRIVATE BETA or PRODUCTION-READY.

### Operate the static site

The static site has no process to restart and no database to back up. Its exact six source files and synthetic assets are versioned in Git; preserve the reviewed source commit or the matching static-only ZIP. Update/recover by creating a Pages Direct Upload deployment with only `deploy/showcase/`, then verify HTTPS, hashes, headers and the demo label. Use deployment history to roll back once a later version exists; the initial immutable alias above records the first release. Do not connect Git, add Functions/bindings, upload a full repository, or publish the functional frontend as part of a static update.

The deployed static assets are eligible for the current Free allowance; no paid feature was selected. This is a current-plan assessment, not a guarantee about future provider pricing or account changes. Recheck before upgrades, domain purchases, dynamic services or adding paid integrations. The staged backend sizing is only a proposal and has not been provisioned.
