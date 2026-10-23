"""Command line interface with CI-friendly exit codes."""

import argparse
from pathlib import Path
import sys

from . import __version__
from .audit import audit


def _positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline preflight checks for image-text SFT datasets.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check a training dataset and optional evaluation split")
    check.add_argument("train", type=Path)
    check.add_argument("--eval", dest="evaluation", type=Path)
    check.add_argument("--image-root", type=Path, help="Common image root; defaults to each dataset's directory")
    check.add_argument("--eval-image-root", type=Path, help="Override the evaluation image root")
    check.add_argument("--max-pixels", type=_positive_int, default=40_000_000)
    check.add_argument("--group-key", help="Require a top-level group field and disjoint groups across splits")
    check.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
    check.add_argument("--output", type=Path, help="Write a new report file; create parent directories, never overwrite")
    check.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
    split = commands.add_parser("split", help="Create audited source/image/input-disjoint train/eval splits")
    split.add_argument("source", type=Path)
    split.add_argument("--output", required=True, type=Path, help="New output directory")
    split.add_argument("--group-key", required=True)
    split.add_argument("--image-root", type=Path)
    split.add_argument("--eval-fraction", type=float, default=0.2, help="Fraction of independent components, not rows")
    split.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.command == "split":
            from .split import split_dataset
            import json
            manifest = split_dataset(args.source, args.output, group_key=args.group_key,
                                     eval_fraction=args.eval_fraction, seed=args.seed,
                                     image_root=args.image_root)
            print(json.dumps({"output": str(args.output), "counts": manifest["counts"],
                              "components": manifest["components"]}))
            return 0
        report = audit(args.train, evaluation=args.evaluation,
                       image_root=args.image_root, eval_image_root=args.eval_image_root,
                       max_pixels=args.max_pixels, group_key=args.group_key)
        rendered = report.render(args.format) + "\n"
        if args.output:
            # Exclusive creation prevents accidental replacement of inputs or reports.
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
            print(f"Report written to {args.output.resolve()}", file=sys.stderr)
        else:
            sys.stdout.write(rendered)
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"vlm-data-doctor: {error}", file=sys.stderr)
        return 2
    return int(report.errors > 0 or (args.strict and report.warnings > 0))
