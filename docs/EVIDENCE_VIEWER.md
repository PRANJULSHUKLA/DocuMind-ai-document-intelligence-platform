# Private Read & Ask workspace

Open a document from Documents to read its original PDF beside the assistant.
Use the page input, Previous/Next, zoom and Fit width controls. On small screens,
Document, Chat and Evidence tabs share the same conversation and reading state.
Answer source buttons open the cited page and show the exact context passage.
Search uses stored OCR chunks, including scanned PDFs, without embedding/model calls.

## Endpoints and authorization

- `GET /files/{id}/view`: authorized reading metadata and current revision.
- `GET /files/{id}/content?version=...`: bounded private PDF bytes, no-store caching,
  ownership before file access, path/symlink validation and current hash checking.
- `GET /files/{id}/search?q=...&after=-1&limit=20`: escaped literal OCR search,
  limited to the workspace, document and completed run. Maximum query 200 characters,
  maximum response 25 passages; `next_after` supports subsequent batches.

Sources add optional file/source IDs, processing-run ID, content_sha256 and the
exact excerpt after context truncation. The old answer/source/timing keys remain.
Missing files return 404; stale revisions or changed original bytes return 409.
PDF reading can precede OCR completion, while questions/search require completion.

## Additive provenance

New uploads store SHA-256 of their original bytes. A worker validates those bytes
before processing and again before publication, and stores the digest on the run's
chunks. No existing records are backfilled or reprocessed. Legacy completed rows
without a digest remain `legacy_unverified`; reading them never writes a digest.
No bounding-box highlights or automatic claim-verification guarantees are made.

No live migration is required for optional fields. For larger installations,
review a normal scoped search index on chunks `(workspace_id, file_id,
processing_run_id, chunk_index)` before applying it separately. The vector index
and embedding dimensions are unchanged. No live index was applied by this PR.

## Run and verify

Use the original private launch instructions with API and frontend from this
worktree/revision; set UPLOAD_DIR to the existing shared private upload directory
if reading pre-existing local originals. Preserve existing credentials outside Git.
Install dependencies with `npm --prefix frontend ci`; run backend pytest and
frontend test/lint/build. `npm --prefix frontend run test:browser` exercises a real
PDF.js worker/canvas with a synthetic two-page PDF at desktop/mobile widths.

The initial viewer downloads one bounded original (25 MB by default) and renders
one page at a time. It cancels replaced downloads and retains only the active PDF.
Legacy answers without source identity cannot be silently mapped by filename;
ask again for enriched citations. Search results are OCR text and may differ from
native PDF text; search/citation navigation does not invent precise highlights.
