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
read_metadata = app.read_metadata
write_tag = app.write_tag
clear_tag = app.clear_tag
process_images = app.process_images
sync_folder_custom_metadata = app.sync_folder_custom_metadata
exiftool_messages = app.exiftool_messages


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
MP4_MINIMAL = bytes.fromhex(
    "000000186674797069736F6D0000020069736F6D69736F32"
    "000000086D646174"
)


class ImageFilesTests(unittest.TestCase):
    def test_dpi_scale_converts_windows_dpi_to_fixed_pixel_multiplier(self):
        self.assertEqual(app.dpi_scale_from_dpi(96), 1.0)
        self.assertEqual(app.dpi_scale_from_dpi(144), 1.5)
        self.assertEqual(app.dpi_scale_from_dpi(192), 2.0)
        self.assertEqual(app.dpi_scale_from_dpi(288), 3.0)
        self.assertEqual(app.dpi_scale_from_dpi(0), 1.0)

    def test_microsoft_yahei_is_available_as_default_chinese_font_label(self):
        self.assertEqual(app.DEFAULT_FONT_LABEL, "微软雅黑")
        self.assertIn("微软雅黑", app.FONT_OPTIONS)
        self.assertEqual(app.resolve_font_family("微软雅黑"), "Microsoft YaHei")
        self.assertEqual(app.LEGACY_FONT_LABELS["Microsoft YaHei"], "微软雅黑")

    def test_blank_suffix_means_in_place_update_even_when_keep_source_is_selected(self):
        source = Path("C:/temp/source.png")
        with (
            mock.patch.object(
                app,
                "read_metadata",
                return_value=({source: {"subjects": [], "windows_tags": []}}, []),
            ),
            mock.patch.object(app, "write_tag", return_value=(1, [])) as write_tag,
            mock.patch.object(app, "read_tagged", return_value=([source], [])),
            mock.patch.object(app.shutil, "copy2") as copy2,
        ):
            outputs, errors = app.process_images([source], keep_source=True, suffix="")

        self.assertEqual(errors, [])
        self.assertEqual(outputs, [source])
        write_tag.assert_called_once_with([source], title=None, subject=None)
        copy2.assert_not_called()

    def test_blank_suffix_confirmation_is_saved_after_first_acceptance(self):
        with mock.patch.object(app.App, "_load_settings", return_value={}):
            root = app.App()
        try:
            with (
                mock.patch.object(root, "_save_settings") as save_settings,
                mock.patch.object(app.messagebox, "askokcancel", return_value=True) as prompt,
            ):
                self.assertTrue(root.confirm_blank_suffix_overwrite(""))
                self.assertTrue(root.blank_suffix_overwrite_confirmed)
                self.assertTrue(root.confirm_blank_suffix_overwrite(""))

            prompt.assert_called_once()
            save_settings.assert_called_once()
            self.assertEqual(root.mode_value.get(), 0.0)
        finally:
            if root.winfo_exists():
                root.quit_app()

    def test_blank_suffix_cancellation_keeps_the_selected_output_mode(self):
        with mock.patch.object(app.App, "_load_settings", return_value={}):
            root = app.App()
        try:
            root.mode_value.set(1.0)
            with mock.patch.object(app.messagebox, "askokcancel", return_value=False):
                self.assertFalse(root.confirm_blank_suffix_overwrite(""))

            self.assertFalse(root.blank_suffix_overwrite_confirmed)
            self.assertEqual(root.mode_value.get(), 1.0)
        finally:
            if root.winfo_exists():
                root.quit_app()

    def test_high_dpi_layout_scales_window_buttons_and_settings_panel(self):
        with mock.patch.object(app, "get_window_dpi", return_value=192):
            root = app.App()
        try:
            root.update()
            self.assertEqual(root.ui_scale, 2.0)
            self.assertGreaterEqual(root.winfo_width(), app.BASE_WINDOW_WIDTH * 2)

            clear_width = root.clear_button.winfo_width()
            self.assertGreaterEqual(clear_width, 78 * 2)
            mode_toggle = next(
                child
                for child in root.controls.winfo_children()
                if isinstance(child, app.ModeToggle)
            )
            self.assertGreaterEqual(mode_toggle.winfo_width(), 190 * 2)

            root._show_settings_panel()
            root.update()
            window_right = root.winfo_rootx() + root.winfo_width()
            panel_right = root.settings_panel.winfo_rootx() + root.settings_panel.winfo_width()
            self.assertLessEqual(panel_right, window_right)
            self.assertGreater(root.settings_panel.winfo_width(), 0)
        finally:
            if root.winfo_exists():
                root.quit_app()

    @unittest.skipUnless(app.os.name == "nt", "Windows mutex is only used on Windows")
    def test_single_instance_mutex_closes_duplicate_process(self):
        kernel32 = mock.Mock()
        kernel32.CreateMutexW.return_value = 123
        with (
            mock.patch.object(app.ctypes, "WinDLL", return_value=kernel32),
            mock.patch.object(
                app.ctypes,
                "get_last_error",
                return_value=app.ERROR_ALREADY_EXISTS,
            ),
        ):
            handle, acquired = app.acquire_single_instance()

        self.assertIsNone(handle)
        self.assertFalse(acquired)
        kernel32.CloseHandle.assert_called_once_with(123)

    @unittest.skipUnless(app.os.name == "nt", "Windows mutex is only used on Windows")
    def test_single_instance_mutex_keeps_first_process_running(self):
        kernel32 = mock.Mock()
        kernel32.CreateMutexW.return_value = 456
        with (
            mock.patch.object(app.ctypes, "WinDLL", return_value=kernel32),
            mock.patch.object(app.ctypes, "get_last_error", return_value=0),
        ):
            handle, acquired = app.acquire_single_instance()

        self.assertEqual(handle, 456)
        self.assertTrue(acquired)
        kernel32.CloseHandle.assert_not_called()

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
                "-charset",
                "exiftool=UTF8",
                "-api",
                "WindowsWideFile=1",
            ],
        )
        self.assertEqual(arguments[-2], "-@")

    def test_filters_routine_exiftool_status_lines(self):
        messages = exiftool_messages("    2 image files read\nWarning: damaged metadata\n")
        self.assertEqual(messages, ["Warning: damaged metadata"])

    def test_lists_only_supported_media_in_current_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in [
                "b.PNG",
                "a.jpg",
                "clip.mp4",
                "short.MOV",
                "note.txt",
                "movie.avi",
                "fake.jpg_original",
            ]:
                (folder / name).touch()
            (folder / "nested").mkdir()
            (folder / "nested" / "c.jpg").touch()

            self.assertEqual(
                [p.name for p in image_files(folder)],
                ["a.jpg", "b.PNG", "clip.mp4", "short.MOV"],
            )

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
    def test_optional_title_and_subject_are_written_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "metadata.png"
            image.write_bytes(PNG_1X1)

            updated, errors = write_tag(
                [image.resolve()],
                title="夏季碎花裙",
                subject="女士连衣裙",
            )
            self.assertEqual(updated, 1, errors)

            legacy_result = app.run_exiftool_files(
                [
                    "-XMP-dc:Subject+=女士连衣裙",
                    "-overwrite_original_in_place",
                ],
                [image.resolve()],
            )
            self.assertEqual(legacy_result.returncode, 0, legacy_result.stderr)

            updated_again, errors = write_tag(
                [image.resolve()],
                title="夏季碎花裙",
                subject="女士连衣裙",
            )
            self.assertEqual(updated_again, 0, errors)

            metadata, errors = read_metadata([image.resolve()])
            self.assertFalse(errors)
            values = metadata[image.resolve()]
            self.assertEqual(values["title"], "夏季碎花裙")
            self.assertEqual(values["subjects"].count(app.TAG), 1)
            self.assertNotIn("女士连衣裙", values["subjects"])
            self.assertEqual(values["windows_subject"], "女士连衣裙")

            cleared, errors = clear_tag([image.resolve()])
            self.assertEqual(cleared, 1, errors)
            metadata, errors = read_metadata([image.resolve()])
            self.assertFalse(errors)
            cleared_values = metadata[image.resolve()]
            self.assertEqual(cleared_values["title"], "")
            self.assertEqual(cleared_values["subjects"], [])
            self.assertEqual(cleared_values["windows_subject"], "")

    @unittest.skipUnless(EXIFTOOL.exists(), "ExifTool is not installed")
    def test_write_read_and_clear_video_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(MP4_MINIMAL)

            updated, errors = write_tag(
                [video.resolve()],
                title="短视频标题",
                subject="短视频主题",
            )
            self.assertEqual(updated, 1, errors)
            self.assertEqual(read_tagged([video.resolve()])[0], [video.resolve()])
            metadata, errors = read_metadata([video.resolve()])
            self.assertFalse(errors)
            self.assertIn(app.TAG, metadata[video.resolve()]["windows_tags"])

            cleared, errors = clear_tag([video.resolve()])
            self.assertEqual(cleared, 1, errors)
            self.assertEqual(read_tagged([video.resolve()])[0], [])
            metadata, errors = read_metadata([video.resolve()])
            self.assertFalse(errors)
            self.assertEqual(metadata[video.resolve()]["title"], "")
            self.assertEqual(metadata[video.resolve()]["subjects"], [])
            self.assertNotIn(app.TAG, metadata[video.resolve()]["windows_tags"])

    @unittest.skipUnless(EXIFTOOL.exists(), "ExifTool is not installed")
    def test_folder_metadata_sync_updates_all_images_without_adding_ai_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            tagged_image = folder / "tagged.png"
            other_image = folder / "other.png"
            video = folder / "clip.mp4"
            nested = folder / "nested"
            nested.mkdir()
            nested_image = nested / "nested.png"
            for image in (tagged_image, other_image, nested_image):
                image.write_bytes(PNG_1X1)
            video.write_bytes(MP4_MINIMAL)

            updated, errors = write_tag([tagged_image.resolve()])
            self.assertEqual(updated, 1, errors)

            synced, errors = sync_folder_custom_metadata(
                [tagged_image.resolve()],
                title="夏季系列",
                subject="碎花裙",
            )
            self.assertEqual(synced, 2, errors)

            metadata, errors = read_metadata(
                [
                    tagged_image.resolve(),
                    other_image.resolve(),
                    video.resolve(),
                    nested_image.resolve(),
                ]
            )
            self.assertFalse(errors)
            for image in (tagged_image.resolve(), other_image.resolve()):
                self.assertEqual(metadata[image]["title"], "夏季系列")
                self.assertNotIn("碎花裙", metadata[image]["subjects"])
                self.assertEqual(metadata[image]["windows_subject"], "碎花裙")
            self.assertEqual(metadata[video.resolve()]["title"], "")
            self.assertEqual(metadata[nested_image.resolve()]["title"], "")
            self.assertEqual(read_tagged([other_image.resolve()])[0], [])

    def test_supported_video_copy_uses_same_tagging_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "clip.mp4"
            source.write_bytes(b"video fixture")
            destination = Path(tmp) / "clip_AI标记.mp4"

            def tagged_side_effect(paths):
                if paths and paths[0] == destination.resolve():
                    return [destination.resolve()], []
                return [], []

            with (
                mock.patch.object(app, "read_tagged", side_effect=tagged_side_effect),
                mock.patch.object(app, "write_tag", return_value=(1, [])) as write,
            ):
                outputs, errors = process_images(
                    [source],
                    keep_source=True,
                    suffix="_AI标记",
                )

            self.assertEqual(errors, [])
            self.assertEqual(outputs, [destination.resolve()])
            self.assertTrue(source.exists())
            self.assertTrue(destination.exists())
            write.assert_called_once_with(
                [destination.resolve()],
                title=None,
                subject=None,
            )

    @unittest.skipUnless(EXIFTOOL.exists(), "ExifTool is not installed")
    def test_existing_tagged_video_gets_windows_tag_without_second_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip_AI标记.mp4"
            video.write_bytes(MP4_MINIMAL)
            result = app.run_exiftool_files(
                [
                    f"-XMP-dc:Subject+={app.TAG}",
                    "-overwrite_original_in_place",
                ],
                [video.resolve()],
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            outputs, errors = process_images(
                [video],
                keep_source=True,
                suffix="_AI标记",
            )

            self.assertEqual(errors, [])
            self.assertEqual(outputs, [video.resolve()])
            self.assertFalse((Path(tmp) / "clip_AI标记_2.mp4").exists())
            metadata, errors = read_metadata(outputs)
            self.assertFalse(errors)
            self.assertIn(app.TAG, metadata[video.resolve()]["windows_tags"])

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
            root.geometry("760x680")
            root.update()
            window_bottom = root.winfo_rooty() + root.winfo_height()
            progress_bottom = root.progress.winfo_rooty() + root.progress.winfo_height()
            controls_right = root.controls.winfo_rootx() + root.controls.winfo_width()
            clear_right = root.clear_button.winfo_rootx() + root.clear_button.winfo_width()
            subject_entry_right = (
                root.custom_subject_entry.winfo_rootx()
                + root.custom_subject_entry.winfo_width()
            )
            folder_check_right = (
                root.folder_metadata_check.winfo_rootx()
                + root.folder_metadata_check.winfo_width()
            )

            self.assertGreaterEqual(root.result_host.winfo_height(), 80)
            self.assertLessEqual(progress_bottom, window_bottom)
            self.assertLessEqual(clear_right, controls_right)
            self.assertLessEqual(subject_entry_right, controls_right)
            self.assertLessEqual(folder_check_right, controls_right)
            self.assertEqual(root.suffix.get(), "_AI标记")
            self.assertTrue(root.open_output_dir.get())
            self.assertFalse(root.custom_title_enabled.get())
            self.assertFalse(root.custom_subject_enabled.get())
            self.assertFalse(root.folder_metadata_enabled.get())
            self.assertEqual(str(root.custom_title_entry.cget("state")), "disabled")
            self.assertEqual(str(root.custom_subject_entry.cget("state")), "disabled")
            style = app.ttk.Style(root)
            self.assertEqual(
                style.lookup(
                    "Surface.TCheckbutton",
                    "indicatorbackground",
                    ("selected",),
                ),
                root.CHECK_ACTIVE,
            )
            self.assertEqual(
                style.lookup(
                    "Surface.TCheckbutton",
                    "indicatorforeground",
                    ("selected",),
                ),
                "#FFFFFF",
            )

            media = Path("sample.jpg")
            root.result_paths = [media]
            root.tag_status = {media: True}
            root.metadata_info = {
                media: {
                    "title": "夏季标题",
                    "subjects": [app.TAG],
                    "windows_subject": "碎花裙主题",
                }
            }
            root.render_results()
            self.assertIsNotNone(root.result_tree)
            self.assertEqual(
                tuple(root.result_tree["displaycolumns"]),
                ("tag", "title", "subject"),
            )
            self.assertEqual(root.result_tree.heading("tag")["text"], "标记")
            self.assertEqual(root.result_tree.heading("title")["text"], "标题")
            self.assertEqual(root.result_tree.heading("subject")["text"], "主题")
            row = root.result_tree.get_children()[0]
            values = root.result_tree.item(row, "values")
            self.assertEqual(
                values[:3],
                (app.TAG, "夏季标题", "碎花裙主题"),
            )

            root.folder_metadata_enabled.set(True)
            root.on_folder_metadata_toggle()
            self.assertTrue(root.custom_title_enabled.get())
            self.assertTrue(root.custom_subject_enabled.get())
            self.assertEqual(str(root.custom_title_entry.cget("state")), "normal")
            self.assertEqual(str(root.custom_subject_entry.cget("state")), "normal")
        finally:
            root.destroy()

    def test_close_button_routes_to_tray_only_when_enabled(self):
        root = app.App()
        try:
            root.update()
            root.tray_on_close.set(True)
            with mock.patch.object(root, "hide_to_tray") as hide:
                root.on_close_request()
            hide.assert_called_once_with()

            root.tray_on_close.set(False)
            with mock.patch.object(root, "quit_app") as quit_app:
                root.on_close_request()
            quit_app.assert_called_once_with()
        finally:
            if root.winfo_exists():
                root.quit_app()

    def test_tray_on_close_defaults_to_enabled_for_new_install(self):
        with mock.patch.object(app.App, "_load_settings", return_value={}):
            root = app.App()
        try:
            self.assertTrue(root.tray_on_close.get())
        finally:
            if root.winfo_exists():
                root.quit_app()

    def test_tray_icon_uses_floating_bubble_visual_language(self):
        root = app.App()
        try:
            root.update()
            icon = root._tray_icon_image()
            self.assertEqual(icon.size, (64, 64))
            self.assertEqual(icon.mode, "RGBA")
            self.assertGreater(icon.getpixel((32, 32))[3], 0)
            self.assertEqual(icon.getpixel((0, 0))[3], 0)
        finally:
            if root.winfo_exists():
                root.quit_app()

    def test_settings_brand_stays_inside_panel_at_default_height(self):
        root = app.App()
        try:
            root.geometry("760x580")
            root.update()
            root._show_settings_panel()
            root.update()
            brand_bottom = root.settings_brand.winfo_rooty() + root.settings_brand.winfo_height()
            panel_bottom = root.settings_panel.winfo_rooty() + root.settings_panel.winfo_height()
            self.assertLessEqual(brand_bottom, panel_bottom)
            self.assertLessEqual(
                max(button.grid_info()["row"] for button in root.settings_theme_buttons),
                1,
            )
        finally:
            if root.winfo_exists():
                root.quit_app()

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
