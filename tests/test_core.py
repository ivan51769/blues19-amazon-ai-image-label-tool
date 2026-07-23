import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

APP_PATH = Path(__file__).resolve().parents[1] / "blues19-app.py"
SPEC = importlib.util.spec_from_file_location("blues19_app", APP_PATH)
app = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(app)
EXIFTOOL = app.EXIFTOOL
image_files = app.image_files
read_tagged = app.read_tagged
write_tag = app.write_tag
clear_tag = app.clear_tag
process_images = app.process_images
exiftool_messages = app.exiftool_messages


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class ImageFilesTests(unittest.TestCase):
    def test_exiftool_forces_windows_wide_character_file_io(self):
        result = mock.Mock()
        with mock.patch.object(app, "run_exiftool", return_value=result) as run:
            returned = app.run_exiftool_files(
                ["-j", "-XMP-dc:Subject"],
                [Path(r"C:\中文目录\测试图片.png")],
            )

        self.assertIs(returned, result)
        arguments = run.call_args.args[0]
        self.assertEqual(
            arguments[:6],
            [
                "-charset",
                "filename=UTF8",
                "-api",
                "WindowsWideFile=1",
                "-j",
                "-XMP-dc:Subject",
            ],
        )

    def test_filters_routine_exiftool_status_lines(self):
        messages = exiftool_messages("    2 image files read\nWarning: damaged metadata\n")
        self.assertEqual(messages, ["Warning: damaged metadata"])

    def test_lists_only_supported_images_in_current_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ["b.PNG", "a.jpg", "note.txt", "fake.jpg_original"]:
                (folder / name).touch()
            (folder / "nested").mkdir()
            (folder / "nested" / "c.jpg").touch()

            self.assertEqual([p.name for p in image_files(folder)], ["a.jpg", "b.PNG"])

    @unittest.skipUnless(EXIFTOOL.exists(), "ExifTool is not installed")
    def test_write_read_and_no_duplicate_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "测试图片.png"
            image.write_bytes(PNG_1X1)

            updated, errors = write_tag([image.resolve()])
            self.assertEqual(updated, 1, errors)
            self.assertEqual(read_tagged([image.resolve()])[0], [image.resolve()])

            updated_again, errors = write_tag([image.resolve()])
            self.assertEqual(updated_again, 0, errors)

            cleared, errors = clear_tag([image.resolve()])
            self.assertEqual(cleared, 1, errors)
            self.assertEqual(read_tagged([image.resolve()])[0], [])

    @unittest.skipUnless(EXIFTOOL.exists(), "ExifTool is not installed")
    def test_write_read_and_clear_in_unicode_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "中文目录"
            folder.mkdir()
            image = folder / "测试图片.png"
            image.write_bytes(PNG_1X1)

            updated, errors = write_tag([image.resolve()])
            self.assertEqual(updated, 1, errors)
            self.assertEqual(read_tagged([image.resolve()])[0], [image.resolve()])

            cleared, errors = clear_tag([image.resolve()])
            self.assertEqual(cleared, 1, errors)
            self.assertEqual(read_tagged([image.resolve()])[0], [])

    @unittest.skipUnless(EXIFTOOL.exists(), "ExifTool is not installed")
    def test_keep_source_creates_tagged_suffixed_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            source.write_bytes(PNG_1X1)
            outputs, errors = process_images([source], keep_source=True, suffix="_AI标记")

            self.assertEqual(len(outputs), 1, errors)
            self.assertTrue(source.exists())
            self.assertEqual(outputs[0].name, "source_AI标记.png")
            self.assertEqual(read_tagged(outputs)[0], outputs)

    def test_ui_layout_keeps_results_and_status_visible_at_minimum_size(self):
        root = app.App()
        try:
            root.geometry("900x680")
            root.update()
            window_bottom = root.winfo_rooty() + root.winfo_height()
            progress_bottom = root.progress.winfo_rooty() + root.progress.winfo_height()

            self.assertGreaterEqual(root.result_host.winfo_height(), 80)
            self.assertLessEqual(progress_bottom, window_bottom)
            self.assertEqual(root.suffix.get(), "_AI标记")
            self.assertTrue(root.open_output_dir.get())
        finally:
            root.destroy()

    @unittest.skipUnless(EXIFTOOL.exists(), "ExifTool is not installed")
    def test_replace_source_renames_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            source.write_bytes(PNG_1X1)
            outputs, errors = process_images([source], keep_source=False, suffix="_AI标记")

            self.assertEqual(len(outputs), 1, errors)
            self.assertFalse(source.exists())
            self.assertEqual(outputs[0].name, "source_AI标记.png")
            self.assertEqual(read_tagged(outputs)[0], outputs)


if __name__ == "__main__":
    unittest.main()
