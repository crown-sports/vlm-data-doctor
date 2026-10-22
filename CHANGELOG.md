# Changelog

## 0.3.0 — 2026-10-22 · public preview

- Include public fixtures and reproduction material in the source distribution; CI runs its bundled tests outside the checkout.
- Create missing output parent directories for documented nested split destinations; existing split outputs remain protected.
- Add `split`: deterministic source/image/input-connected train/eval exports with row provenance, file hashes and post-split audit. Preserve input files and reject invalid or inseparable datasets.
- Rewrite the English and Chinese guides around export failures, document-level split overlap and changed experiment inputs.
- Add a generated document QA example showing default checks, source-group overlap and a disjoint comparison.
- Document the current algorithms and define the missing evidence for near-duplicate and downstream data-quality work.

## 0.2.0 — 2026-10-02 · public preview

- Add an offline HTML report with severity filters, search, review guidance and a reproducibility manifest.
- Add opt-in `--group-key` checks for group-disjoint train/evaluation splits.
- Add dataset-byte and decoded-image inventory hashes, environment and settings to JSON schema 1.1.
- Reject duplicate JSON keys and handle unpaired Unicode text/path input without a fingerprint crash.
- Publish a labeled synthetic regression corpus, raw CPU timing/RSS runs and generated figures.
- Record a pinned LlamaFactory fixture smoke check and add a synthetic dataset-mapping recipe.
- Expand bilingual documentation with expected outcomes, research protocol, practical integration and limitations.

The synthetic corpus is not independently held out. This release does not claim
model-quality improvements, GPU savings, full trainer compatibility or field adoption.

## 0.1.0 — 2026-10-02 · alpha

- Initial local still-image and text SFT preflight.
- JSON/JSONL, ShareGPT/messages, image validation, exact duplicate/overlap checks.
- Text, JSON and Markdown reports, synthetic examples and cross-platform CI.
