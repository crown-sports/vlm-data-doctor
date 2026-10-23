# Supported validation profile

This profile is for paired supervised conversations with local still images. It
is intentionally stricter and narrower than the union of all trainer formats.

## Input and API

Use a JSON array or JSONL. `messages` turns use `role`/`content` with
`system`/`user`/`assistant`; ShareGPT `conversations` use `from`/`value` with
`system`/`human`/`gpt`. An optional top-level `system` string is also accepted.
There must be at most one initial system turn, followed by user/assistant pairs.
Text-only records can omit `images`; image paths must be local and relative.

```python
from vlm_data_doctor import audit

report = audit("data/train.jsonl", evaluation="data/test.jsonl",
               image_root="data", group_key="document_id")
print(report.render("json"))
```

Omit `group_key` when no group-disjoint policy is required. `eval_image_root`
overrides the common image root for evaluation; without either override, paths
resolve relative to each dataset file. The API returns findings for data defects
and raises exceptions for I/O, encoding and configuration failures.

## Rule catalog

| Code | Level | Interpretation / suggested action |
| --- | --- | --- |
| `invalid_json` | error | Fix JSON syntax; duplicate object keys, NaN and Infinity are rejected. |
| `dataset_schema` | error | Use a JSON array or a `.jsonl` / `.ndjson` file. |
| `empty_dataset` | error | Supply at least one record. |
| `record_schema` | error | Each record must be an object. |
| `conversation_schema` | error | Use exactly one nonempty messages/conversations list of objects. |
| `invalid_role` | error | Use system/user/assistant or system/human/gpt for the selected schema. |
| `invalid_content` | error | Supply nonempty text in conversation turns; content blocks are unsupported. |
| `turn_order` | error | Use paired user/assistant turns with at most one initial system turn. |
| `invalid_id` | error | Optional IDs must be nonempty strings or integers, excluding booleans. |
| `images_schema` | error | Use a list of nonempty path strings. |
| `image_token_mismatch` | error | Match `<image>` marker count to path count. |
| `image_token_role` | error | This profile expects image markers in user turns. |
| `image_path` | error | Use relative forward-slash paths beneath the root; resolved symlinks must stay inside it. |
| `remote_image` | error | Materialize images locally; the auditor does not download them. |
| `missing_image` | error | Locate the referenced file under the configured root. |
| `unreadable_image` | error | Point to a regular, decodable image file. |
| `image_too_large` | error | Resize or review the pixel limit. Pillow safety limits still apply. |
| `animated_image` | error | Extract a still image. |
| `unsupported_modality` | error | Remove audio/video fields or use a suitable auditor. |
| `duplicate_id` | warning | IDs are compared as strings within each split. |
| `duplicate_sample` | warning | Same normalized conversation and ordered image bytes within a split. |
| `split_sample_overlap` | error | Same full sample in train and evaluation. |
| `split_input_overlap` | warning | Same non-assistant turns and image bytes, but different answers. |
| `split_image_overlap` | warning | Same image bytes across splits; review task-specific grouping. |
| `invalid_group` | error | When `--group-key` is selected, every record needs that field as a nonempty string or integer. |
| `split_group_overlap` | error | A selected source/document/topology group appears across train and evaluation. |

## Overlap semantics

Image overlap means exact file bytes, not decoded-pixel or semantic equality.
The first observed training row is used as the reference. Each evaluation row
gets at most one image-overlap finding per unique image digest. Invalid rows may
still contribute successfully decoded image hashes to the image-overlap check,
but never contribute full sample or input fingerprints.

Full samples combine **all** roles and text with the ordered image hashes.
Input comparisons omit assistant turns. This also catches the same question and
images paired with different answers. For multi-turn conversations this input
definition is a review heuristic: previous assistant turns can change context.

IDs do not define samples. Identical IDs across different splits are not, by
themselves, treated as leakage. Unicode NFC, CRLF normalization and outer trimming
are applied to text; internal whitespace remains significant.

A warning needs review, not automatic deletion. In particular, image-disjoint,
document-disjoint, source-disjoint and topology-disjoint splits answer different
scientific questions. Choose the policy before interpreting model scores.

## Report contract

Schema version `1.1` reports counts of source records (including malformed JSONL
records), successfully decoded unique resolved image-file paths, and findings.
Findings include severity, code, dataset (`train`/`eval`), row, field and advice.
Source conversation contents, ID values and image filenames are not echoed.
Operational I/O errors use stderr and may contain filesystem paths.

Version 1.1 adds `provenance` without removing the earlier summary/issue fields.
It contains tool/profile/Python/Pillow versions, max-pixel and group settings,
SHA-256 of each dataset's exact file bytes, and a SHA-256 of the sorted list of
successfully decoded image-file hashes. The image list uses one entry per unique
resolved path, so identical bytes at two different paths appear twice. Its
serialization uses compact JSON separators and UTF-8. File names and absolute
paths are excluded. Missing/corrupt images are not covered by that image digest.

`--group-key` selects an exact top-level field name, not a nested selector. Group
values are type-sensitive and not normalized; an integer and its string spelling
are different groups. This policy is opt-in because group-disjoint evaluation is
not appropriate for every task. Structurally invalid rows can still establish a
valid group identity, while early schema failures may prevent the row from
receiving a group-overlap finding. Correct structural errors before treating the
audit as a complete split review.

Text with unpaired Unicode surrogates is rejected as invalid content instead of
failing later during fingerprint encoding. HTML output escapes report content and
uses a restrictive content security policy with a fixed script hash; the report
does not load external assets. Large reports include all rows in the DOM, so JSON
is preferable for very large issue sets.

More than one finding can refer to a record; finding counts are not failed-record
counts. Reports use input order and do not include timestamps, so the same input
and environment produce deterministic output.

## Operational limits

- The default limit is 40 million pixels per image. `--max-pixels` changes it;
  Pillow's own decompression protection still applies. Animated images are rejected.
- JSONL is read row by row, but sample/image indexes and findings remain in memory.
  JSON arrays load in full. This is not a bounded-memory dataset pipeline.
- JSONL locations are physical line numbers, including blank lines in the count.
  JSON-array rows are one-based positions; row 0 identifies a dataset-level issue.
- Text, JSON, Markdown and HTML output are supported. On main, missing report
  directories are created and the saved path is printed to stderr. In v0.3.0,
  create the parent directory first. Both refuse to overwrite a file. Exit `1` still writes the report;
  exit `2` indicates a CLI, configuration, I/O, encoding or report-writing failure.
- Keep inputs unchanged during an audit: hashing and validation read them separately.
  The manifest records fingerprints, not a recoverable dataset snapshot.
- Tool calls, preference/RL records, video/audio, remote images, structured content
  blocks and arbitrary field remapping are outside this profile.
- Passing does not verify answer correctness, privacy, data licensing, tokenizer
  behavior or training success. Run a small training smoke test with your actual stack.

## Find a report and recover from a failed run

For the README's v0.3.0 checkout, create an output folder before using a nested path:

```bash
python -c "from pathlib import Path; Path('reports/run-1').mkdir(parents=True, exist_ok=True)"
vlm-data-doctor check examples/broken/train.jsonl --eval examples/broken/validation.jsonl --image-root examples/clean --format html --output reports/run-1/audit.html
```

Open `reports/run-1/audit.html` relative to the directory where you ran the command.
Exit `1` is expected here: the report contains the four fixture findings. Fix a
reported row, then write the next report to a new path such as `reports/run-2/audit.html`.
Keep earlier reports when you rerun the check.

If the command exits `2`, read stderr before looking for a report. Check the input
path, the image root and whether the output file already exists. Malformed JSON
inside a readable dataset is a finding (`invalid_json`, exit `1`), so inspect its
reported row. A successful text-only check is also valid; images are optional.
