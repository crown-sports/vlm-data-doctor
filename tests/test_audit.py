import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

from vlm_data_doctor import audit
from vlm_data_doctor.cli import main


def sample(image="red.png", answer="red", question="<image>What color is this?"):
    return {"messages": [{"role": "user", "content": question},
                         {"role": "assistant", "content": answer}],
            "images": [image]}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        Image.new("RGB", (16, 16), "red").save(self.root / "red.png")
        Image.new("RGB", (16, 16), "blue").save(self.root / "blue.png")

    def write(self, rows, name="train.jsonl"):
        path = self.root / name
        payload = (json.dumps(rows) if path.suffix == ".json"
                   else "\n".join(json.dumps(row) for row in rows) + "\n")
        path.write_text(payload, encoding="utf-8")
        return path

    def run_audit(self, rows):
        return audit(self.write(rows))

    def codes(self, report):
        return {issue.code for issue in report.issues}

    def test_clean_jsonl(self):
        report = self.run_audit([sample()])
        self.assertEqual((report.errors, report.warnings, report.unique_image_files), (0, 0, 1))

    def test_json_array(self):
        report = audit(self.write([sample()], "train.json"))
        self.assertEqual(report.records, {"train": 1})
        self.assertEqual(report.errors, 0)

    def test_sharegpt(self):
        report = self.run_audit([{"system": "Answer briefly.", "images": ["red.png"],
                                 "conversations": [{"from": "human", "value": "<image>Color?"},
                                                   {"from": "gpt", "value": "Red."}]}])
        self.assertEqual(report.errors, 0)

    def test_text_only_and_initial_system(self):
        report = self.run_audit([{"messages": [{"role": "system", "content": "Be brief"},
                                                {"role": "user", "content": "Hello"},
                                                {"role": "assistant", "content": "Hi"}]}])
        self.assertEqual(report.errors, 0)

    def test_multi_turn_multi_image(self):
        row = sample()
        row["messages"] += [{"role": "user", "content": "<image>And this?"},
                            {"role": "assistant", "content": "Blue"}]
        row["images"].append("blue.png")
        self.assertEqual(self.run_audit([row]).errors, 0)

    def test_image_token_mismatch(self):
        self.assertIn("image_token_mismatch", self.codes(self.run_audit([sample(question="Color?")])))

    def test_tokens_in_assistant_rejected(self):
        self.assertIn("image_token_role", self.codes(self.run_audit([sample(answer="<image>")])))

    def test_missing_image(self):
        self.assertIn("missing_image", self.codes(self.run_audit([sample(image="missing.png")])))

    def test_corrupt_image(self):
        (self.root / "bad.png").write_bytes(b"not an image")
        self.assertIn("unreadable_image", self.codes(self.run_audit([sample(image="bad.png")])))

    def test_truncated_jpeg(self):
        path = self.root / "truncated.jpg"
        Image.new("RGB", (100, 100)).save(path)
        path.write_bytes(path.read_bytes()[:-50])
        self.assertIn("unreadable_image", self.codes(self.run_audit([sample(image=path.name)])))

    def test_directory_is_not_image(self):
        self.assertIn("unreadable_image", self.codes(self.run_audit([sample(image=".")])))

    def test_pixel_limit(self):
        report = audit(self.write([sample()]), max_pixels=200)
        self.assertIn("image_too_large", self.codes(report))

    def test_animated_image(self):
        frames = [Image.new("RGB", (8, 8), color) for color in ("red", "blue")]
        frames[0].save(self.root / "animated.gif", save_all=True, append_images=frames[1:])
        self.assertIn("animated_image", self.codes(self.run_audit([sample(image="animated.gif")])))

    def test_absolute_and_windows_paths(self):
        for path in [str(self.root / "red.png"), "C:/red.png", "C:\\red.png", "dir\\red.png"]:
            with self.subTest(path=path):
                self.assertIn("image_path", self.codes(self.run_audit([sample(image=path)])))

    def test_parent_path_escape(self):
        self.assertIn("image_path", self.codes(self.run_audit([sample(image="../outside.png")])))

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "external.png"
            Image.new("RGB", (8, 8)).save(target)
            try:
                (self.root / "escape.png").symlink_to(target)
            except OSError:
                self.skipTest("Symlink creation unavailable on this platform")
            self.assertIn("image_path", self.codes(self.run_audit([sample(image="escape.png")])))

    def test_symlink_inside_root(self):
        try:
            (self.root / "alias.png").symlink_to(self.root / "red.png")
        except OSError:
            self.skipTest("Symlink creation unavailable on this platform")
        self.assertEqual(self.run_audit([sample(image="alias.png")]).errors, 0)

    def test_url_is_not_fetched(self):
        for path in ["https://example.invalid/image.png", "data:image/png;base64,AAAA"]:
            with self.subTest(path=path):
                self.assertIn("remote_image", self.codes(self.run_audit([sample(image=path)])))

    def test_bad_record_types_do_not_crash(self):
        for row in [None, 3, [], "text"]:
            with self.subTest(row=row):
                self.assertIn("record_schema", self.codes(self.run_audit([row])))

    def test_both_conversation_schemas_rejected(self):
        row = sample()
        row["conversations"] = []
        self.assertIn("conversation_schema", self.codes(self.run_audit([row])))

    def test_invalid_role_types(self):
        for role in [[], {}, None, "tool"]:
            row = sample()
            row["messages"][0]["role"] = role
            with self.subTest(role=role):
                self.assertIn("invalid_role", self.codes(self.run_audit([row])))

    def test_structured_content_is_explicitly_unsupported(self):
        row = sample()
        row["messages"][0]["content"] = [{"type": "image_url", "image_url": "red.png"}]
        self.assertIn("invalid_content", self.codes(self.run_audit([row])))

    def test_blank_answer(self):
        self.assertIn("invalid_content", self.codes(self.run_audit([sample(answer="  \n")])))

    def test_wrong_turn_order(self):
        row = sample()
        row["messages"].reverse()
        self.assertIn("turn_order", self.codes(self.run_audit([row])))

    def test_unanswered_prompt(self):
        row = sample()
        row["messages"].pop()
        self.assertIn("turn_order", self.codes(self.run_audit([row])))

    def test_duplicate_system_prompt(self):
        row = sample()
        row["system"] = "First system"
        row["messages"].insert(0, {"role": "system", "content": "Second system"})
        self.assertIn("turn_order", self.codes(self.run_audit([row])))

    def test_invalid_images_types(self):
        for images in [None, {}, "red.png", [5], [""]]:
            row = sample()
            row["images"] = images
            with self.subTest(images=images):
                self.assertIn("images_schema", self.codes(self.run_audit([row])))

    def test_unsupported_modalities(self):
        for key in ["videos", "audios"]:
            row = sample()
            row[key] = ["clip"]
            with self.subTest(key=key):
                self.assertIn("unsupported_modality", self.codes(self.run_audit([row])))

    def test_duplicate_sample_ignores_id_and_filename(self):
        shutil.copyfile(self.root / "red.png", self.root / "copy.png")
        first, second = sample(), sample(image="copy.png")
        first["id"], second["id"] = "one", "two"
        report = self.run_audit([first, second])
        self.assertEqual(report.warnings, 1)
        self.assertIn("duplicate_sample", self.codes(report))

    def test_duplicate_id_is_separate_warning(self):
        first, second = sample(), sample(image="blue.png", answer="blue")
        first["id"], second["id"] = "same", "same"
        self.assertEqual(self.codes(self.run_audit([first, second])), {"duplicate_id"})

    def test_train_eval_overlap_after_renaming_image(self):
        shutil.copyfile(self.root / "red.png", self.root / "renamed.png")
        train = self.write([sample()])
        validation = self.write([sample(image="renamed.png")], "eval.jsonl")
        report = audit(train, evaluation=validation)
        self.assertEqual(report.errors, 1)
        self.assertEqual(self.codes(report), {"split_sample_overlap", "split_image_overlap"})

    def test_same_input_different_label_flags_review(self):
        report = audit(self.write([sample()]), evaluation=self.write([sample(answer="blue")], "eval.jsonl"))
        self.assertEqual(report.errors, 0)
        self.assertIn("split_input_overlap", self.codes(report))

    def test_same_image_new_question_is_warning(self):
        validation = self.write([sample(question="<image>Is there a cat?", answer="No")], "eval.jsonl")
        report = audit(self.write([sample()]), evaluation=validation)
        self.assertEqual(self.codes(report), {"split_image_overlap"})

    def test_different_image_same_question_no_overlap(self):
        report = audit(self.write([sample()]), evaluation=self.write([sample(image="blue.png", answer="blue")], "eval.jsonl"))
        self.assertEqual(report.issues, [])

    def test_invalid_record_does_not_establish_sample_overlap(self):
        row = sample(image="missing.png")
        report = audit(self.write([row]), evaluation=self.write([row], "eval.jsonl"))
        self.assertNotIn("split_sample_overlap", self.codes(report))

    def test_unicode_normalization_across_schemas(self):
        first = {"messages": [{"role": "user", "content": "café"}, {"role": "assistant", "content": "yes"}]}
        second = {"conversations": [{"from": "human", "value": "  cafe\u0301  "}, {"from": "gpt", "value": "yes"}]}
        self.assertIn("duplicate_sample", self.codes(self.run_audit([first, second])))

    def test_jsonl_keeps_physical_line_numbers_and_continues(self):
        path = self.write([sample()])
        path.write_text("\nnot json\n" + json.dumps(sample()) + "\n", encoding="utf-8")
        report = audit(path)
        self.assertEqual(report.records["train"], 2)
        self.assertEqual(report.issues[0].row, 2)
        self.assertEqual(report.unique_image_files, 1)

    def test_bom_supported(self):
        path = self.write([sample()])
        path.write_text("\ufeff" + path.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(audit(path).errors, 0)

    def test_nonstandard_json_constants_rejected(self):
        path = self.root / "train.jsonl"
        path.write_text('{"value": NaN}\n', encoding="utf-8")
        self.assertEqual(self.codes(audit(path)), {"invalid_json"})

    def test_empty_input(self):
        for name in ["train.json", "train.jsonl"]:
            with self.subTest(name=name):
                self.assertIn("empty_dataset", self.codes(audit(self.write([], name))))

    def test_json_object_instead_of_array(self):
        path = self.root / "train.json"
        path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.codes(audit(path)), {"dataset_schema"})

    def test_separate_eval_image_root(self):
        separate = self.root / "eval-images"
        separate.mkdir()
        Image.new("RGB", (16, 16), "green").save(separate / "green.png")
        report = audit(self.write([sample()]), evaluation=self.write([sample(image="green.png", answer="green")], "eval.jsonl"),
                       eval_image_root=separate)
        self.assertEqual(report.issues, [])

    def test_invalid_configuration(self):
        train = self.write([sample()])
        for kwargs in [{"max_pixels": 0}, {"max_pixels": True}, {"eval_image_root": self.root},
                       {"image_root": self.root / "not-found"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                audit(train, **kwargs)

    def test_json_report_does_not_include_training_content(self):
        report = self.run_audit([sample(answer="private response", image="missing.png")])
        result = report.render("json")
        self.assertNotIn("private response", result)
        self.assertEqual(json.loads(result)["schema_version"], "1.1")

    def test_markdown_report(self):
        report = self.run_audit([sample(image="missing.png")])
        self.assertIn("| error | missing_image | train:1 images[0] |", report.render("markdown"))

    def invoke(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            status = main(list(args))
        return status, output.getvalue(), error.getvalue()

    def test_cli_success_and_json(self):
        status, output, _ = self.invoke("check", str(self.write([sample()])), "--format", "json")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output)["summary"]["errors"], 0)

    def test_cli_error_exit(self):
        self.assertEqual(self.invoke("check", str(self.write([sample(image="missing.png")])))[0], 1)

    def test_cli_strict_warning_exit(self):
        train = str(self.write([sample(), sample()]))
        self.assertEqual(self.invoke("check", train)[0], 0)
        self.assertEqual(self.invoke("check", train, "--strict")[0], 1)

    def test_cli_io_error_exit(self):
        status, output, error = self.invoke("check", str(self.root / "not-found.jsonl"))
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("vlm-data-doctor:", error)

    def test_cli_refuses_to_overwrite_dataset(self):
        path = self.write([sample()])
        original = path.read_bytes()
        self.assertEqual(self.invoke("check", str(path), "--output", str(path))[0], 2)
        self.assertEqual(path.read_bytes(), original)

    def test_cli_writes_new_report(self):
        path = self.root / "report.json"
        self.assertEqual(self.invoke("check", str(self.write([sample()])), "--format", "json", "--output", str(path))[0], 0)
        self.assertEqual(json.loads(path.read_text())["summary"]["errors"], 0)

    def test_cli_nested_report_preserves_findings_and_refuses_rerun(self):
        path = self.root / "reports" / "first" / "audit.json"
        train = self.write([sample(image="missing.png")])
        args = ("check", str(train), "--format", "json", "--output", str(path))
        status, output, error = self.invoke(*args)
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertIn(str(path.resolve()), error)
        self.assertGreater(json.loads(path.read_text())["summary"]["errors"], 0)
        original = path.read_bytes()
        self.assertEqual(self.invoke(*args)[0], 2)
        self.assertEqual(path.read_bytes(), original)

    def test_cli_does_not_create_output_parent_for_missing_input(self):
        output = self.root / "reports" / "audit.json"
        self.assertEqual(self.invoke("check", str(self.root / "absent.jsonl"),
                                     "--output", str(output))[0], 2)
        self.assertFalse(output.parent.exists())


if __name__ == "__main__":
    unittest.main()
