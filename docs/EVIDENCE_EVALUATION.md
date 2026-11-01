# Reproducible evidence evaluation

Run from the repository root, with no credentials or services:

```sh
python -m app.evaluation.quality
python -m pytest tests/test_quality_evaluation.py -q
```

The versioned ten-case synthetic dataset includes single/multi-document questions,
missing and conflicting evidence, and intentional bad observations: retrieval miss,
wrong page, stale run, fabricated quotation, unsupported claim and foreign document.
The checked-in replay is a **negative-control evaluator fixture**, not recorded
Gemini output and not a claim about production accuracy. Tests additionally exercise
the real RAG source builder at the mocked generation boundary.

One earlier synthetic live invoice response is also recorded separately. Its input
artifact and PDF hashes were checked against the saved validation manifest before
annotation. Reproduce its **returned-source/target-claim** score with:

```sh
python -m app.evaluation.quality --dataset evaluation/recorded-live-gold-v1.json --observations evaluation/recorded-live-observations-v1.json
```

Both expected targets (USD 100.00 and December 1, 2026) occur in the answer and
the independently authored invoice passage; the single returned source has the
correct file/page/published run/hash and exact quotation. All applicable metrics
are 1.0 for this one case; abstention is null. Recorded response time is5221.72ms,
including1153.23ms retrieval and4068.36ms generation. Usage for this response was
not individually recorded. This is historical main revision b3ea363, not a fresh
run on these PRs. One easy, one-page case cannot estimate general accuracy.
Raw retrieval candidates were not saved, so this is returned-source recall rather
than a measurement of Atlas ranking recall. The target-only annotation does not
claim exhaustive coverage of every possible claim in a free-form answer.

To score separately collected real results, pass `--dataset` and `--observations`
JSON paths with the same schema. Gold annotations must be authored independently
of generated answers. Each claim's exact text and all required source IDs must be
annotated. Citation checks require retrieved identity, file, page, run, hash and an
exact quotation. This does not infer arbitrary semantic entailment. Recall and
precision are micro-averaged over unique source IDs. Scope isolation is per case.
Abstention requires both an explicit flag and no claims. Zero-denominator metrics
are null. Latency and usage are reported only if supplied by the observation; do
not populate them with invented values. Evaluator runtime is not retrieval latency.

There is deliberately no provider runner in this phase: it cannot spend quota or
retry exhausted services. Any future live collector must explicitly cap requests,
input/output tokens and monetary spend using verified provider pricing, disable
retries for evaluation, and stop on the first 429. Existing application retry and
fallback settings are unchanged. Never load private customer data into fixtures.
