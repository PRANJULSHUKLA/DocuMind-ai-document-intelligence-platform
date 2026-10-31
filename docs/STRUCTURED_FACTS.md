# Published evidence facts

Authenticated `POST /collections/{collection_id}/facts` accepts
`{"file_ids": ["<member-file-id>"]}`. One to five distinct completed, owned
collection members are allowed. Existing collection/document authorization and
post-read consistency checks are reused. No model request, embedding, re-ingestion,
new storage or migration occurs.

Response facts contain typed amounts/currencies, unambiguous dates, explicit
`Buyer: Name.` style parties, obligations in a small English grammar, and qualifier
text. Each carries the complete exact sentence, character offsets, chunk/file/page,
published run/hash and document revision. Conditions and interpretation uncertainty
are explicit. Conflicting observations remain separate, never silently reconciled.
Missing fields mean not observed in the bounded sample, not absent from the PDF.

Bounds: five documents, first 20 chunks each, 4,000 characters/chunk, 1,000
characters/sentence and 200 facts. Limits reached are reported. Incomplete trailing
sentences are ignored. Legacy documents without published run and hash produce an
explicit limitation and no facts. Provenance binds OCR to a published version;
it does not establish OCR accuracy or cryptographic verification of historical data.

Use the existing authenticated frontend session/API client to POST the request, or
the forthcoming comparison interface. This phase is an API/module, not a new UI.
The regression fixtures in `tests/test_structured_facts.py` demonstrate USD 1,200.50,
December 1, 2026, an explicit named buyer and a qualified supplier obligation.
No general entity resolution, table extraction, inferred parties or legal
interpretation is claimed. More document types require reviewed fixtures first.
