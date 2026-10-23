# VLM Data Doctor

Check an image-text dataset before the training run: find broken records, then split related pages together.

[![CI](https://github.com/crown-sports/vlm-data-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/crown-sports/vlm-data-doctor/actions/workflows/ci.yml)
[Python 3.10+](pyproject.toml) · [v0.3.1 preview](https://github.com/crown-sports/vlm-data-doctor/releases/tag/v0.3.1) · [MIT](LICENSE)

[简体中文](README.zh-CN.md) · [Quick start](#try-the-report) · [Checks](docs/checks.md) · [LlamaFactory](docs/integrations/llamafactory.md)

A missing image or a misplaced `<image>` marker is easier to fix before a job starts.
Data Doctor checks local SFT exports and gives you an HTML report with the row,
field and suggested fix. It also catches exact overlap between train and eval.

![v0.3.0 report: three errors and one warning, each with a location and suggested fix](docs/assets/audit-v0.3.png)

*Actual report from the included faulty fixture: 3 errors, 1 warning. Runs on CPU; no model or external API.*

## Try the report

```bash
git clone --branch v0.3.1 https://github.com/crown-sports/vlm-data-doctor.git
cd vlm-data-doctor
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\Activate.ps1` in PowerShell, then:

```bash
python -m pip install .
vlm-data-doctor check examples/broken/train.jsonl --eval examples/broken/validation.jsonl --image-root examples/clean --format html --output report.html
```

Open `report.html`. This fixture deliberately fails, so the command returns `1`
after writing the report. Use a new output filename for each run.

For a passing example:

```bash
vlm-data-doctor check examples/clean/train.jsonl --eval examples/clean/validation.jsonl --strict
```

Expected: 2 train records, 1 eval record, no errors or warnings.

## Keep pages of one document together

Different pages can come from the same manual. If your evaluation is meant to test
unseen documents, keep those pages on the same side of the split.

![Split manifest: manual A's two pages in train, manual B in eval; zero findings after the split](docs/assets/split-result.png)

*Visualization of a real `manifest.json` from the generated manual example. The CLI writes JSONL and JSON files.*

```bash
vlm-data-doctor split examples/document-split/all.jsonl --group-key document_id --eval-fraction 0.2 --seed 42 --output manual-split
vlm-data-doctor check manual-split/train.jsonl --eval manual-split/eval.jsonl --image-root examples/document-split --group-key document_id --strict
```

You get `train.jsonl`, `eval.jsonl` and `manifest.json`: original row numbers,
assignments, hashes and the final check. The destination must be new; missing
parent directories are created automatically.

Rows stay together when they share a document ID, identical image bytes or
identical normalized inputs, including transitive connections. The ratio applies
to these connected groups, so **20% does not mean exactly 20% of rows**. Images
are not copied; keep using the original image root.
[Walk through the example](examples/document-split/README.md).

## Check your export

Accepts JSON arrays or JSONL with `messages` or ShareGPT `conversations`:

```json
{
  "document_id": "manual-a",
  "messages": [
    {"role": "user", "content": "<image>What color is this square?"},
    {"role": "assistant", "content": "Red."}
  ],
  "images": ["images/red.png"]
}
```

```bash
vlm-data-doctor check data/train.jsonl --eval data/test.jsonl --image-root data --group-key document_id --format json --output audit.json
```

Replace the paths with yours. Images resolve relative to the dataset file unless
an image root is supplied. `document_id` is only required when selected with
`--group-key`. Exit codes: `0` no errors, `1` data errors, `2` configuration/I/O error;
`--strict` also fails on warnings. Missing report parent directories are created automatically; existing reports are preserved.

The checks cover format, image decoding and exact overlap. They do not judge
answer quality or find cropped/recompressed near duplicates.

[Report paths and recovery](docs/checks.md#find-a-report-and-recover-from-a-failed-run) · [Full rules and Python API](docs/checks.md) · [LlamaFactory setup](docs/integrations/llamafactory.md) · [Benchmarks](docs/benchmarks.md) · [Implementation notes](docs/product.md) · [Image sources](docs/screenshots.md)

[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [Citation](CITATION.cff)
