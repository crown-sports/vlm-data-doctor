# README images

`assets/audit-v0.3.png` is a browser screenshot of the v0.3.0 HTML report generated
from the included faulty fixture. It shows all four findings, without changing
the report or its numbers. Chrome viewport: 1200 × 1320.

From the repository root, with Data Doctor installed:

```bash
vlm-data-doctor check examples/broken/train.jsonl --eval examples/broken/validation.jsonl --image-root examples/clean --format html --output audit.html
```

Exit `1` is expected. Open `audit.html` in a browser.

`assets/split-result.svg` and its PNG rendering visualize the CLI's manifest;
they are not a screenshot of an additional application screen. The labels,
counts, source rows and filenames are read from the real output and checked
against the included source file's SHA-256. Use this documentation checkout for
the rendering helper, which was added after the v0.3.0 tag:

```bash
vlm-data-doctor split examples/document-split/all.jsonl --group-key document_id --eval-fraction 0.2 --seed 42 --output manual-split
python docs/render_split_example.py manual-split/manifest.json split-result.svg
```

Render the SVG at 1200 × 580 for the PNG. Both examples use generated images,
not third-party documents. Original older screenshots remain in `assets/` for
links from earlier documentation.
