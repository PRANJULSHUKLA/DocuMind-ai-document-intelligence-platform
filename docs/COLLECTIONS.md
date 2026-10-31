# Collections and multi-document questions

Originally reviewed as a stack after the Evidence Viewer. The owner authorized
sequential release merges; see `RELEASE_REVIEW.md` for verification and exact
backend, worker, and frontend launch commands from the merged main worktree.

Collections are additive records in `document_collections` with `workspace_id`,
`name`, `file_ids`, `revision`, and `created_at`. Removing membership or deleting a
collection never removes original documents. Create/list/edit/delete routes live
under `/collections`; POST `/{id}/chat` accepts question and optional `file_ids`.
Edit uses an expected revision and returns 409 for stale clients.

Each collection/question has at most ten documents. Only completed authorized
members are retrieved, using one query embedding and at most three results per
member through the existing Atlas vector index. The existing four-chunk/8000
character generation budget remains. All retrievals include workspace and file
filters and honor published run/hash. Membership/version changes during generation
reject the response. Failed/processing members are reported separately. Sources
identify their original document and open its private Evidence Viewer.

Bulk upload uses independent existing upload requests, up to ten PDFs per action;
a failed file does not roll back accepted files. The UI refreshes statuses every
five seconds. Uploads remain in Documents until explicitly added to a collection.

No production schema/index/data writes have been made. MongoDB creates the new
collection on first authorized create. Before production rollout, an administrator
may add a normal compound index `{workspace_id: 1, _id: -1}` for listing; it is
not applied by startup or this feature. The existing Atlas vector index requires
workspace_id/file_id/processing_run_id filter fields as documented for the baseline.
Collection lists currently show the latest 100 records. No pagination UI yet.
