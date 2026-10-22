# Product value and evidence

[English README](../README.md) · [中文首页](../README.zh-CN.md)

## The decision this supports

For people preparing image-text fine-tuning data, the first decision is whether an
export is ready to submit to training, and whether its evaluation split matches
the intended experiment. A row-level report lets a dataset owner repair concrete
records; a split manifest lets an experiment reviewer inspect what was assigned.

A useful first outcome is a readable report or a checked split, not a higher model
score. Start with the bundled examples, then audit one real export before adding
the command to a training pipeline. A passing report covers the documented rules.

## Current advantages, with inspectable evidence

| Capability | Why it matters | Implementation and evidence |
| --- | --- | --- |
| Image decoding, conversation and marker checks in one offline pass | Find broken multimodal records before a training job consumes them | [audit.py](../src/vlm_data_doctor/audit.py), [audit tests](../tests/test_audit.py) |
| Row/field findings, JSON and offline HTML, input fingerprints | A colleague can locate the issue and identify the exact checked input | [report.py](../src/vlm_data_doctor/report.py), [HTML renderer](../src/vlm_data_doctor/html_report.py), [evidence tests](../tests/test_evidence.py) |
| Split connected evidence together | Shared image bytes or normalized inputs can connect different document IDs transitively; a simple row shuffle or document-only grouping misses those links | [split.py](../src/vlm_data_doctor/split.py), [split tests](../tests/test_split.py) cover transitive links, reordered input, inseparable data and image-root reuse |

The engineering value is the combination of explicit rules, safe outputs and an
inspectable split audit. Hashing and connected components are established methods;
this project does not claim a new duplicate-detection algorithm. The recorded
[benchmark](benchmarks.md) contains 128 rule-targeted synthetic findings and 32 clean
controls, plus a CPU scale experiment. It does not establish accuracy on unseen
customer datasets or downstream model improvement.

## Use your own export

1. Keep image paths valid and choose the source unit before splitting: document,
   patient, scene or another unit appropriate to your evaluation. Supply its ID;
   the tool does not infer source identity.
2. Run `check`, inspect findings, and repair upstream data. If creating a split,
   run `split` and retain its manifest alongside the experiment.
3. Recheck exported files with the original image root. Images are not copied;
   relocating the dataset requires updating that root. Inspect absolute paths in
   the manifest before sharing it.
4. Add `--strict` to a training gate only when warnings should block that workflow.
   See [rules and exit codes](checks.md) and [LlamaFactory integration](integrations/llamafactory.md).

## Limits and what could become a durable advantage

Current checks cannot judge answer correctness or detect recompressed/cropped or
semantic near duplicates. Rows are loaded into memory; component-level split
fractions need not match row fractions. A fully connected dataset cannot produce
an independent evaluation set and is rejected.

A defensible advantage would require a growing, independently labeled collection
of real export failures, measured false positives/misses, and maintained training
format integrations. Those are future evidence to accumulate, not a moat already
established by the current synthetic suite. [Acceptance criteria](roadmap.md).
