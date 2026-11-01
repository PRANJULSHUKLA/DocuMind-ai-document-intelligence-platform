# Bounded validated obligation comparison

In Collections, select two to five completed documents, check **Use validated
obligation comparison (bounded)**, and compare. The authenticated endpoint is
`POST /collections/{id}/compare-semantic`, with the same file_ids/focus body as
the original comparator. The original endpoint and default UI mode are preserved.

This mode reads the bounded published OCR fact sample without embeddings or LLM
calls. Focus labels the report; it does not retrieve additional passages in this
mode. Review extracted typed facts in the expandable evidence section. Both the
original literal findings and new normalized-obligation findings retain clickable
quotations and document-version provenance. Limits/skips remain visible.

Supported normalization: must/shall/is required to, explicit prohibitions, ISO
currency values and unambiguous dates, and `make payment of` → `pay`. This is a
small reviewed grammar, not a general semantic equivalence engine. Matching party
labels and action structures are required. Party aliases are not resolved. Every
qualified clause abstains; differing parties/paraphrases produce missing or
insufficient evidence. Opposite polarity is only a **possible** contradiction.
Conflicting observations within a document abstain. Different aligned values are
an observed difference, never automatically a contradiction.

`tests/test_semantic_comparison.py` provides nine representative positive,
negative and ambiguous examples plus provenance and endpoint regressions. Run
`python -m pytest tests/test_semantic_comparison.py -v` to reproduce. These are
known-context synthetic cases, not live retrieval or general language accuracy.

No costly semantic model fallback is enabled while quota availability is unknown.
Expanding coverage requires independent annotated examples and evidence validation;
similarity alone will never establish contractual equivalence. This draft depends
on the structured-facts PR and must not be merged before its base is approved.
