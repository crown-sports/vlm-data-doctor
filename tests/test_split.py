import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from vlm_data_doctor import audit
from vlm_data_doctor.cli import main
from vlm_data_doctor.split import split_dataset


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'data.jsonl'

    def write(self, rows):
        self.source.write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def row(self, group, question=None, image=None):
        return {'document_id': group, 'messages': [
            {'role': 'user', 'content': ('<image>' if image else '') + (question or f'Question {group}?')},
            {'role': 'assistant', 'content': 'Answer'}], 'images': [image] if image else []}

    def split(self, name='split', **kwargs):
        return split_dataset(self.source, self.root / name, group_key='document_id', **kwargs)

    def test_preserves_rows_groups_and_reproducibility(self):
        rows = [self.row('a'), self.row('a', 'Page two?'), self.row('b'), self.row('c')]
        self.write(rows)
        before = self.source.read_bytes()
        result = self.split()
        self.assertEqual(sum(result['counts'].values()), 4)
        self.assertEqual(result, self.split('again'))
        train = [json.loads(x) for x in (self.root / 'split/train.jsonl').read_text().splitlines()]
        evaluation = [json.loads(x) for x in (self.root / 'split/eval.jsonl').read_text().splitlines()]
        self.assertFalse({r['document_id'] for r in train} & {r['document_id'] for r in evaluation})
        self.assertCountEqual(train + evaluation, rows)
        self.assertEqual(before, self.source.read_bytes())
        with self.assertRaises(FileExistsError):
            self.split()

    def test_image_and_input_components_are_transitive(self):
        Image.new('RGB', (8, 8), 'red').save(self.root / 'red.png')
        (self.root / 'copy.png').write_bytes((self.root / 'red.png').read_bytes())
        rows = [self.row('a', image='red.png'), self.row('b', image='copy.png'),
                self.row('b', 'same'), self.row('c', 'same'), self.row('d')]
        self.write(rows)
        result = self.split(eval_fraction=0.5)
        self.assertEqual(result['components'], 2)
        for indices in result['source_rows'].values():
            self.assertTrue(set(indices) in ({1, 2, 3, 4}, {5}))
        report = audit(self.root / 'split/train.jsonl', evaluation=self.root / 'split/eval.jsonl',
                       image_root=self.root, group_key='document_id')
        self.assertFalse(any(i.code.startswith('split_') for i in report.issues))

    def test_typed_group_ids_and_reordered_rows_keep_assignments(self):
        rows = [self.row(1), self.row('1', 'Different?'), self.row('other')]
        self.write(rows)
        result = self.split()
        self.write(list(reversed(rows)))
        again = self.split('again')
        self.assertEqual(result['components'], 3)
        self.assertEqual(result['component_assignments'], again['component_assignments'])

    def test_recheck_from_other_cwd_uses_recorded_image_root(self):
        Image.new('RGB', (8, 8), 'red').save(self.root / 'red.png')
        Image.new('RGB', (8, 8), 'blue').save(self.root / 'blue.png')
        self.write([self.row('a', image='red.png'), self.row('b', image='blue.png')])
        manifest = self.split()
        previous = Path.cwd()
        try:
            os.chdir(self.root / 'split')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['check', 'train.jsonl', '--eval', 'eval.jsonl',
                                       '--image-root', manifest['image_root'],
                                       '--group-key', 'document_id', '--strict']), 0)
        finally:
            os.chdir(previous)

    def test_invalid_or_inseparable_data_publishes_nothing(self):
        for rows in [[self.row('a'), self.row('a', 'Two?')], [self.row('a', image='absent.png')], [{}]]:
            self.write(rows)
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.split()
            self.assertFalse((self.root / 'split').exists())

    def test_cli_creates_nested_output_parent_without_overwriting_a_split(self):
        self.write([self.row('a'), self.row('b')])
        output = self.root / 'splits' / 'run-42'
        args = ['split', str(self.source), '--group-key', 'document_id', '--output', str(output)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        self.assertEqual(set(before), {'train.jsonl', 'eval.jsonl', 'manifest.json'})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 2)
        self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_cli_and_configuration(self):
        self.write([self.row('a'), self.row('b')])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['split', str(self.source), '--group-key', 'document_id',
                                   '--output', str(self.root / 'cli')]), 0)
        for fraction in [0, 1, float('nan'), True]:
            with self.subTest(fraction=fraction), self.assertRaises(ValueError):
                self.split(eval_fraction=fraction)
