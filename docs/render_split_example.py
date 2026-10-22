"""Draw the README's split example from a CLI-produced manifest (stdlib only)."""

import argparse
import hashlib
import html
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("manifest", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
source = Path(__file__).resolve().parents[1] / "examples/document-split/all.jsonl"
manifest = json.loads(args.manifest.read_text())
if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["source_sha256"]:
    raise SystemExit("Manifest must describe the included document-split example")
rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
parts = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="580" viewBox="0 0 1200 580">',
    '<rect width="1200" height="580" fill="#f4f7f6"/>',
    "<style>text{font-family:Arial,sans-serif;fill:#172f33}.small{font-size:18px;fill:#52696f}.label{font-size:20px;font-weight:bold}.title{font-size:34px;font-weight:bold}</style>",
    '<text x="44" y="54" class="small">VLM DATA DOCTOR · DOCUMENT-SPLIT EXAMPLE</text>',
    '<text x="44" y="107" class="title">Keep pages of the same manual together.</text>',
]
for side, x, color in [("train", 44, "#177c68"), ("eval", 620, "#476eb6")]:
    indices = manifest["source_rows"][side]
    count_label = "record" if len(indices) == 1 else "records"
    parts.extend(
        [
            f'<rect x="{x}" y="142" width="536" height="300" rx="14" fill="white" stroke="#d9e3e1"/>',
            f'<rect x="{x}" y="142" width="536" height="7" rx="3" fill="{color}"/>',
            f'<text x="{x + 26}" y="190" class="label">{side.upper()} · {manifest["counts"][side]} {count_label}</text>',
        ]
    )
    for i, index in enumerate(indices):
        row = rows[index - 1]
        group = html.escape(str(row[manifest["group_key"]]))
        filename = html.escape(Path(row["images"][0]).name)
        y = 225 + i * 91
        parts.extend(
            [
                f'<rect x="{x + 24}" y="{y}" width="488" height="74" rx="8" fill="#f2f6f5"/>',
                f'<text x="{x + 42}" y="{y + 29}" class="label">{group} · source row {index}</text>',
                f'<text x="{x + 42}" y="{y + 55}" class="small">{filename}</text>',
            ]
        )
summary = manifest["audit"]["summary"]
parts.extend(
    [
        f'<text x="44" y="486" class="label">{manifest["components"]} independent components · seed {manifest["seed"]} · {summary["errors"]} errors · {summary["warnings"]} warnings after split</text>',
        '<text x="44" y="526" class="small">Generated manuals · drawn from manifest.json; the CLI writes JSONL + JSON, not this view.</text>',
        '<text x="44" y="555" class="small">The 20% eval target selects components. It does not guarantee 20% of rows.</text>',
        "</svg>",
    ]
)
args.output.write_text("\n".join(parts))
