# PR #2 finalization: upload reliability and private development

This follow-up is limited to dispatch reliability, recovery, and repeatable local
configuration. It contains no Evidence Viewer or content-fingerprint migration.

## Failure and resulting behavior

Previously, a queue exception always caused the API to delete the uploaded PDF.
Redis could already have accepted the job, leaving an accepted job with no input.

The original is now saved atomically through a same-directory temporary file.
Dispatch state and an attempt number are recorded before enqueue. The deterministic
job ID is `documind-<file_id>-attempt-<n>`. RQ 2.10's atomic `unique=True` enqueue
prevents duplicate queue entries. Reconciliation reads the exact job and validates
its queue, function, arguments, and attempt; it does not use Queue.fetch_job's
destructive missing-job cleanup.

Accepted work returns normal success. Unknown acceptance returns 202 with the saved
file ID. A job observed absent or terminal returns a retryable 503 with that ID.
The original is retained in every post-save dispatch outcome. Conditional updates
cannot regress a processing/completed/failed worker to a queued state.

## Retry and fencing

An authenticated workspace-scoped retry endpoint resumes the existing saved file.
Unknown queue state does not start another attempt. A missing unacknowledged job
reuses its original ID. A known terminal job or a failed processing attempt advances
the attempt number with a MongoDB compare-and-set, so concurrent requests cannot
both reserve the next attempt. Worker claims and state updates include that attempt
as a fencing token; delayed older jobs cannot publish over the new run. Existing
two-argument jobs still work against legacy records without attempt metadata.

An active processing lease blocks recovery. An expired lease with confirmed
terminal/absent work can be recovered explicitly. A completed document is a no-op.
The UI keeps the saved ID on dispatch failure and provides processing retry rather
than a second upload. Bounded background reconciliation covers pending dispatches;
OCR/model failures are not automatically rerun.

## Orphan handling

`scripts/recover_uploads.py` defaults to dry-run. It targets only aged, unconfirmed,
new-protocol uploads and limits its batch size. `--apply` can recover durable
originals using the same service/ownership metadata, or conditionally mark a record
with no usable original failed after queue absence/termination is confirmed. It
does not purge originals, reset databases, reassign documents, scan ZIP contents,
or replay unrelated failed model jobs. No live recovery scan/application was run
as part of this change.

## Development configuration

The existing `/api` Vite proxy is retained with loopback binding. Preview proxy
inheritance is explicitly disabled. An explicit production API base is unchanged.
README commands reproduce the actual per-process development settings without
editing or committing credentials. Private port forwarding is required; a public
development proxy must not front development authentication.

## Validation and review boundaries

Validation includes complete backend/frontend suites, RAG/analysis/workflow and
authorization regressions, lost acknowledgements, queue absence/outage, fast-worker
races, concurrent terminal retries, worker fencing, atomic-write failure cleanup,
orphan recovery dry-run/apply, and saved-document UI retries. A real RQ test uses
only a randomly named isolated queue, executes no jobs/models, and removes its own
test jobs/queue afterward.

Final local verification in the existing Python 3.11 / Node 22 Dev Container:

| Check | Result |
|---|---|
| Complete backend suite | 103 passed |
| Complete frontend suite | 11 passed |
| Frontend lint and production build | Passed |
| Explicit production API URL build | Passed |
| Python dependency consistency and syntax/whitespace checks | Passed |
| Real RQ accepted-job timeout and concurrent unique enqueue | Passed; isolated test queue removed |

Two existing third-party backend deprecation warnings remain. The new commits
have not been pushed; GitHub CI must validate their exact head after push approval.

The pre-existing direct-SDK edits in document_intelligence/workflow agents and the
risk-engine newline edit are excluded from these commits. The established committed
Gemini retry/fallback integration is unchanged. The untracked ZIP is untouched.

Push and merge both require the user's explicit approval. Updated GitHub CI must
pass after an approved push before merging. Managed OIDC callback/renewal/logout
verification remains a production-release requirement rather than a blocker to
private local development. Known operational limitations such as quotas, backups,
and adaptive extraction remain separate milestones.
