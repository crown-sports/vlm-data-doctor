"""Reproducible splits that keep source and exact-evidence components together."""

import json
import math
from pathlib import Path
import shutil
import tempfile

from .audit import _digest, _file_digest, _normalize, _read_rows, audit
from .report import Report


def split_dataset(source: str | Path, output: str | Path, *, group_key: str,
                  eval_fraction: float = 0.2, seed: int = 0,
                  image_root: str | Path | None = None) -> dict:
    """Write new JSONL splits and a manifest, preserving every valid input row.

    Rows are connected by source group, identical image bytes, or normalized
    non-assistant turns with the same ordered images. The fraction applies to
    components, not rows. Data must fit in memory. Images are not copied.
    """
    if not isinstance(group_key, str) or not group_key.strip():
        raise ValueError('group_key must be a nonempty top-level field name')
    if isinstance(eval_fraction, bool) or not isinstance(eval_fraction, (int, float)) or not 0 < eval_fraction < 1:
        raise ValueError('eval_fraction must be between 0 and 1')
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed must be an integer')
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError(f'Output must be a new directory: {output}')
    root = Path(image_root).resolve() if image_root is not None else source.resolve().parent
    initial = audit(source, image_root=root, group_key=group_key)
    if initial.errors:
        raise ValueError(f'Input has {initial.errors} errors; run check and repair it before splitting')
    read_report = Report(records={'source': 0})
    rows = list(_read_rows(source, 'source', read_report))
    if read_report.errors:
        raise ValueError('Input changed while reading; retry with a stable source')
    parents = list(range(len(rows)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right):
        left, right = find(left), find(right)
        parents[max(left, right)] = min(left, right)

    seen = {}
    image_hashes = {}
    group_hashes = []
    for index, (_, record) in enumerate(rows):
        group = _digest([type(record[group_key]).__name__, record[group_key]])
        group_hashes.append(group)
        images = []
        for path in record.get('images', []):
            resolved = (root / path).resolve()
            if resolved not in image_hashes:
                image_hashes[resolved] = _file_digest(resolved)
            images.append(image_hashes[resolved])
        messages_key = 'messages' if 'messages' in record else 'conversations'
        role_key, text_key = ('role', 'content') if messages_key == 'messages' else ('from', 'value')
        role_map = {'human': 'user', 'gpt': 'assistant'}
        turns = [('system', _normalize(record['system']))] if record.get('system', '').strip() else []
        turns.extend((role_map.get(m[role_key], m[role_key]), _normalize(m[text_key]))
                     for m in record[messages_key])
        inputs = _digest([[turn for turn in turns if turn[0] != 'assistant'], images])
        keys = [('group', group), ('input', inputs), *[('image', value) for value in images]]
        for key in keys:
            if key in seen:
                union(index, seen[key])
            else:
                seen[key] = index
    components = {}
    for index in range(len(rows)):
        components.setdefault(find(index), []).append(index)
    if len(components) < 2:
        raise ValueError('Need at least two independent components; groups/images/inputs connect all rows')
    component_ids = {key: _digest(sorted({group_hashes[i] for i in indices}))
                     for key, indices in components.items()}
    ordered = sorted(components, key=lambda key: (_digest([seed, component_ids[key]]), component_ids[key]))
    count = min(len(ordered) - 1, max(1, math.ceil(len(ordered) * eval_fraction)))
    eval_components = set(ordered[:count])
    partitions = {'train': [], 'eval': []}
    assignments = {'train': [], 'eval': []}
    for index, (line, record) in enumerate(rows):
        label = 'eval' if find(index) in eval_components else 'train'
        partitions[label].append(record)
        assignments[label].append(line)
    # Validate staging before publishing; no incomplete dataset on validation failure.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vlm-split-', dir=output.parent) as folder:
        staging = Path(folder)
        for label, records in partitions.items():
            (staging / f'{label}.jsonl').write_text(
                ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        checked = audit(staging / 'train.jsonl', evaluation=staging / 'eval.jsonl',
                        image_root=root, group_key=group_key)
        if checked.errors or any(issue.code.startswith('split_') for issue in checked.issues):
            raise ValueError('Split failed overlap validation; no outputs were published')
        if _file_digest(source) != initial.provenance['dataset_sha256']['train']:
            raise ValueError('Input changed during splitting; retry with a stable source')
        if any(_file_digest(path) != digest for path, digest in image_hashes.items()):
            raise ValueError('An image changed during splitting; retry with stable inputs')
        manifest = {
            'schema_version': 1, 'algorithm': 'source-image-input-components-v1',
            'source_sha256': _file_digest(source), 'group_key': group_key,
            'seed': seed, 'requested_eval_component_fraction': eval_fraction,
            'image_root': str(root), 'components': len(components),
            'counts': {label: len(records) for label, records in partitions.items()},
            'source_rows': assignments,
            'component_assignments': {component_ids[key]: ('eval' if key in eval_components else 'train')
                                      for key in sorted(components, key=lambda k: component_ids[k])},
            'split_sha256': {label: _file_digest(staging / f'{label}.jsonl') for label in partitions},
            'audit': checked.to_dict(),
        }
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        output.mkdir()  # Exclusive destination creation, including collision races.
        try:
            for path in staging.iterdir():
                path.rename(output / path.name)
        except OSError:
            shutil.rmtree(output)
            raise
    return manifest
