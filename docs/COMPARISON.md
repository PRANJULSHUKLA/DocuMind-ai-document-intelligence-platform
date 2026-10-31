# Evidence-grounded comparison

This feature is stacked on Collections, which is stacked on Evidence Viewer.
Review in that order. None of the feature PRs is authorized for merge.

Open Collections, select a collection, and choose two to five completed members
in Compare documents. A focus controls retrieval. POST
`/collections/{id}/compare` accepts `file_ids` and `focus` and returns a versioned
structured result with findings, per-document facts, evidence IDs, source passages,
classification counts, method, and limitations. Every evidence button opens the
private original page and retains the comparison on return.

The first release deliberately uses deterministic fact extraction rather than
free-form model comparison. It recognizes explicit ISO-currency-code amounts,
ISO dates or English full-month dates, and unconditional `must`/`shall` obligations.
It reuses one embedding and the existing authorized retrieval service. At most two
700-character passages per selected document (8000 total characters) are compared;
no generation call is made. Findings are capped at 30. Membership and processing
versions are rechecked before returning the response.

- Supported agreement means the extracted values match, not contractual equivalence.
- Supported difference means the explicit value sets differ, not a contradiction.
- Possible contradiction requires the same explicit subject and action with opposite
  required/prohibited polarity. Human review of scope and exceptions is required.
- Missing information means a fact was not found in retrieved passages. It never
  claims that the fact is absent from the full original document.
- Insufficient evidence covers unrecognized/ambiguous facts and conflicting
  obligation polarities within one document.

Different wording alone never establishes contradiction. Conditional obligations,
ambiguous numeric dates, symbol-only currency amounts, inferred obligations, and
semantic paraphrase comparison are not interpreted. Retrieval may miss a relevant
passage. Focused semantic comparison and full-document fact coverage are future
work requiring their own evaluated evidence validation; this release makes no
claim to provide them. Legacy provenance remains explicitly unverified.

No new database fields, indexes, migrations or stored model outputs are required.
The existing Gemini fallback/retry integration, single-document chat, analysis and
workflow implementations are preserved. Tests cover numerical differences,
normalized dates, missing information, ambiguous and opposite obligations,
workspace/member authorization, processing state, API flow and browser navigation.
