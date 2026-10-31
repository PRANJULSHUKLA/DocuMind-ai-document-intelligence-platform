# Engineering milestone — October 31, 2026

## Outcome

Established reproducible builds and offline tests, added managed OIDC sign-in and
personal workspace isolation, and hardened ingestion and evidence handling.
Existing React/FastAPI/Gemini/MongoDB/RQ architecture and endpoint response shapes
remain in use. Document endpoints now require identity; that is an intentional
security change.

## Changes

- Fixed the assistant import's filename casing and frontend lint errors.
- Connected upload completion to the existing library update/refresh handler.
- Added backend and browser tests plus a Linux GitHub Actions workflow.
- Added OIDC Authorization Code/PKCE browser sign-in and backend RS256 verification.
- Scoped listing, detail, status, analysis, workflow, and retrieval by workspace.
- Added explicit metadata response models and removed stored Markdown/internal
  fields from metadata responses.
- Added bounded ingestion leases, per-run chunk staging, publication guards,
  failed-run cleanup, and version-scoped retrieval.
- Ensured returned sources describe only context actually supplied to the model.
- Enforced the configured similarity threshold and removed résumé-specific bias
  from the active chat prompt.
- Moved blocking generation/embedding, upload writing, and enqueue calls off the
  asynchronous request event loop.
- Removed raw workflow/provider output and token-bearing Axios objects from logs.
- Added private shared upload-directory configuration and a worker entry point
  that uses the API's configured Redis connection.
- Added an ownership migration tool that defaults to dry-run and an index
  definition generator that never modifies Atlas.
- Applied compatible dependency fixes for all initially reported high-severity
  npm advisories. Six moderate findings remain in ESLint's development dependency
  chain; npm reports no compatible automatic fix. No forced major overrides used.

## Validation

- Backend tests passed on macOS Python 3.11 and a clean Linux Python 3.11 container.
- Frontend tests, lint, and production build passed on macOS and a clean Linux
  Node 22 container using `npm ci`.
- `pip check`, shell syntax checks, and `git diff --check` passed.
- Atlas connection and configured Gemini model metadata were verified.
- Added only `workspace_id` and `processing_run_id` filter fields to the existing
  live Atlas `vector_index`, preserving its 3072-dimensional embedding definition.
  Subsequent live retrieval successfully used those filters.
- One synthetic PDF passed real upload/RQ enqueue, Vision OCR, embedding,
  completed-run publication, Atlas retrieval, answer/source generation,
  structured analysis/risk rules, and workflow planning.
- Smoke validation used a temporary localhost Valkey queue. The synthetic MongoDB
  file/chunk records, temporary upload files, and queue container were removed.
  Existing document contents and ownership were not migrated or reset.
- Managed provider callback/logout behavior remains an integration prerequisite:
  no provider application existed during this milestone. Offline token signature,
  claims, expiry, cross-user access, and local-mode tests passed.

## Runtime prerequisites

1. Configure the managed identity provider using [SIGN_IN.md](SIGN_IN.md), or use
   explicit loopback-only development mode while developing locally.
2. Run a reachable Valkey service and the background worker. The smoke queue was
   temporary; it is not a permanent runtime service.
3. Install fresh platform-local dependencies. Existing copied Linux virtual
   environments and `node_modules` must not be reused on macOS.
4. Intentionally assign legacy documents to a verified owner after backup and
   dry-run review. They remain hidden by default.
5. Keep API/worker upload storage private, shared, persistent, and backed up.

## Remaining roadmap

This milestone is not the entire production roadmap. Remaining work includes
adaptive native-text extraction, page/memory limits, authenticated document
preview and highlighting, measured retrieval/citation quality, team membership
and roles, persistent actions and approvals, request/usage quotas, cost telemetry,
monitoring, tested backup/recovery, deployment/rollback, and pilot validation.
Workflow generation still reruns analysis. Analysis still reads only the first
30,000 characters; this needs explicit coverage reporting or a larger-document
strategy before relying on exhaustive findings.

The backend currently emits two third-party test deprecation warnings
(AnyIO/pytest and Starlette/httpx). They do not fail the suite.

## Rollback

Revert the code milestone to restore prior application behavior, recognizing
that this also removes authentication protection. The additive Atlas filter
fields are compatible with the previous retrieval query and can remain. No
document migration is required to roll back because no existing ownership/content
was changed. Do not remove ownership from real user documents as a rollback step.
