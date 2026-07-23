from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import ctypes
from queue import Empty, Queue
from pathlib import Path
from tkinter import filedialog, font as tkfont, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD


TAG = "contains-synthetic-performer"
DEFAULT_SUFFIX = "_AI标记"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
APP_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
EXIFTOOL = RESOURCE_DIR / "tools" / "exiftool.exe"
CHUNK_SIZE = 100
SETTINGS_FILE = (
    Path(os.environ.get("APPDATA", str(Path.home())))
    / "blues19-ai-image-label-tool"
    / "blues19-settings.json"
)
THEMES = {
    "RainbowText": {
        "name": "冰川蓝",
        "canvas": "#E8F8FF",
        "surface": "#F8FDFF",
        "ink": "#17435A",
        "muted": "#608597",
        "border": "#A8DEEE",
        "action": "#32ADD7",
        "hover": "#238FAF",
        "soft": "#DDF3FB",
        "active": "#356A80",
        "rainbow": ("#FF892F", "#FF3091", "#9E4BFF", "#46C4FF"),
    },
    "FrostedGlass": {
        "name": "磨砂玻璃",
        "canvas": "#F0F3F5",
        "surface": "#FCFDFD",
        "ink": "#34464F",
        "muted": "#7B8B92",
        "border": "#D3DDE1",
        "action": "#829FAA",
        "hover": "#6B8995",
        "soft": "#E9EEF0",
        "active": "#566F79",
        "rainbow": ("#839DA7", "#9CB0B7", "#B1C1C7", "#C6D1D5"),
    },
    "NeonBlue": {
        "name": "霓虹蓝",
        "canvas": "#071B2B",
        "surface": "#0B2940",
        "ink": "#EAF8FF",
        "muted": "#A7CADC",
        "border": "#247BA8",
        "action": "#10B7FF",
        "hover": "#0095D6",
        "soft": "#123C55",
        "active": "#145B7D",
        "rainbow": ("#35E6FF", "#48B9FF", "#8A8CFF", "#D369FF"),
    },
    "OrangeGradient": {
        "name": "橙粉",
        "canvas": "#FFF4E8",
        "surface": "#FFFCF7",
        "ink": "#4A2B20",
        "muted": "#805E50",
        "border": "#F2AE72",
        "action": "#EF7B45",
        "hover": "#D86431",
        "soft": "#FDE4D1",
        "active": "#8C4628",
        "rainbow": ("#FF8B38", "#FF6F61", "#F05C93", "#CD65C8"),
    },
    "PinkGradient": {
        "name": "粉紫",
        "canvas": "#FFF0F8",
        "surface": "#FFFAFD",
        "ink": "#4D2942",
        "muted": "#7F5B70",
        "border": "#E8A4C9",
        "action": "#D85DA7",
        "hover": "#B9478C",
        "soft": "#F8DCEC",
        "active": "#79375F",
        "rainbow": ("#FF73B9", "#E967D1", "#B66EF0", "#7F8CFF"),
    },
}
FONT_OPTIONS = ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "SimHei")
ACCENT_TEXT_OPTIONS = ("七彩渐变", "主题色", "深墨色", "柔和灰")
GRADIENT_TEXT_COLORS = (
    "#FF8A3D",
    "#FF5D68",
    "#FF3E9D",
    "#C54DDB",
    "#895CF2",
    "#4C90E9",
    "#38C6D9",
)


def enable_high_dpi() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


enable_high_dpi()


def _colorref(hex_color: str) -> ctypes.c_int:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return ctypes.c_int(red | (green << 8) | (blue << 16))


def apply_windows_glass(
    window: tk.Misc,
    *,
    caption_color: str,
    text_color: str,
    border_color: str,
    dark: bool,
) -> None:
    """Use the Windows 11 backdrop when available; silently retain the themed fallback."""
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        hwnd = int(window.winfo_id())
        user32 = ctypes.windll.user32
        user32.GetParent.restype = ctypes.c_void_p
        parent = user32.GetParent(ctypes.c_void_p(hwnd))
        if parent:
            hwnd = int(parent)
        backdrop = ctypes.c_int(3)  # DWMSBT_TRANSIENTWINDOW: acrylic-like backdrop
        corner = ctypes.c_int(2)  # DWMWCP_ROUND
        dark_mode = ctypes.c_int(1 if dark else 0)
        caption = _colorref(caption_color)
        caption_text = _colorref(text_color)
        window_border = _colorref(border_color)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 34, ctypes.byref(window_border), ctypes.sizeof(window_border)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 35, ctypes.byref(caption), ctypes.sizeof(caption)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 36, ctypes.byref(caption_text), ctypes.sizeof(caption_text)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 33, ctypes.byref(corner), ctypes.sizeof(corner)
        )
    except (AttributeError, OSError, tk.TclError):
        pass


def image_files(folder: Path) -> list[Path]:
    return sorted(
        (p.resolve() for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
        key=lambda p: p.name.lower(),
    )


def validate_suffix(value: str) -> str:
    suffix = value.strip()
    if not suffix:
        raise ValueError("文件名尾缀不能为空。")
    if re.search(r'[<>:"/\\|?*]', suffix) or suffix.endswith((".", " ")):
        raise ValueError('文件名尾缀不能包含 < > : " / \\ | ? *，也不能以点或空格结尾。')
    return suffix


def suffixed_path(source: Path, suffix: str) -> Path:
    if source.stem.endswith(suffix):
        return source
    candidate = source.with_name(f"{source.stem}{suffix}{source.suffix}")
    number = 2
    while candidate.exists():
        candidate = source.with_name(f"{source.stem}{suffix}-{number}{source.suffix}")
        number += 1
    return candidate


def run_exiftool(args: list[str]) -> subprocess.CompletedProcess[str]:
    if not EXIFTOOL.exists():
        raise FileNotFoundError(f"缺少组件：{EXIFTOOL}")
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(
        [str(EXIFTOOL), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startupinfo,
        check=False,
    )


def run_exiftool_files(args: list[str], paths: list[Path]) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".args", delete=False) as handle:
        arg_file = Path(handle.name)
        for path in paths:
            handle.write(str(path) + "\n")
    try:
        return run_exiftool(["-charset", "filename=UTF8", *args, "-@", str(arg_file)])
    finally:
        arg_file.unlink(missing_ok=True)


def exiftool_messages(stderr: str) -> list[str]:
    routine = re.compile(r"^\s*\d+\s+image files?\s+(?:read|updated|unchanged)\s*$", re.IGNORECASE)
    return [line.strip() for line in stderr.splitlines() if line.strip() and not routine.match(line)]


def read_tagged(paths: list[Path]) -> tuple[list[Path], list[str]]:
    if not paths:
        return [], []
    tagged: list[Path] = []
    errors: list[str] = []
    for start in range(0, len(paths), CHUNK_SIZE):
        chunk = paths[start : start + CHUNK_SIZE]
        result = run_exiftool_files(["-j", "-XMP-dc:Subject"], chunk)
        errors.extend(exiftool_messages(result.stderr))
        try:
            records = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"无法读取 ExifTool 返回结果：{exc}") from exc
        for record in records:
            subjects = record.get("Subject", [])
            if isinstance(subjects, str):
                subjects = [subjects]
            if TAG in subjects:
                tagged.append(Path(record["SourceFile"]).resolve())
    return tagged, errors


def write_tag(paths: list[Path]) -> tuple[int, list[str]]:
    if not paths:
        return 0, []
    already_tagged, errors = read_tagged(paths)
    tagged_set = set(already_tagged)
    pending = [p for p in paths if p not in tagged_set]
    for start in range(0, len(pending), CHUNK_SIZE):
        chunk = pending[start : start + CHUNK_SIZE]
        result = run_exiftool_files(
            [f"-XMP-dc:Subject+={TAG}", "-overwrite_original_in_place"], chunk
        )
        errors.extend(exiftool_messages(result.stderr))
    verified, verify_errors = read_tagged(pending)
    errors.extend(verify_errors)
    return len(verified), errors


def clear_tag(paths: list[Path]) -> tuple[int, list[str]]:
    if not paths:
        return 0, []
    errors: list[str] = []
    tagged, read_errors = read_tagged(paths)
    errors.extend(read_errors)
    for start in range(0, len(tagged), CHUNK_SIZE):
        chunk = tagged[start : start + CHUNK_SIZE]
        result = run_exiftool_files(
            [f"-XMP-dc:Subject-={TAG}", "-overwrite_original_in_place"], chunk
        )
        errors.extend(exiftool_messages(result.stderr))
    remaining, verify_errors = read_tagged(tagged)
    errors.extend(verify_errors)
    remaining_set = set(remaining)
    cleared = len([path for path in tagged if path not in remaining_set])
    return cleared, errors


def process_images(paths: list[Path], keep_source: bool, suffix: str) -> tuple[list[Path], list[str]]:
    suffix = validate_suffix(suffix)
    outputs: list[Path] = []
    errors: list[str] = []
    for source in paths:
        source = source.resolve()
        try:
            tagged, read_errors = read_tagged([source])
            errors.extend(read_errors)
            if source.stem.endswith(suffix) and tagged:
                outputs.append(source)
                continue

            destination = suffixed_path(source, suffix)
            if keep_source:
                shutil.copy2(source, destination)
                _, write_errors = write_tag([destination])
                errors.extend(write_errors)
                verified, verify_errors = read_tagged([destination])
                errors.extend(verify_errors)
                if not verified:
                    destination.unlink(missing_ok=True)
                    errors.append(f"写入后复查失败：{source}")
                    continue
            else:
                _, write_errors = write_tag([source])
                errors.extend(write_errors)
                verified, verify_errors = read_tagged([source])
                errors.extend(verify_errors)
                if not verified:
                    errors.append(f"写入后复查失败：{source}")
                    continue
                if destination != source:
                    source.rename(destination)
            outputs.append(destination)
        except Exception as exc:
            errors.append(f"{source}：{exc}")
    return outputs, errors


class GradientText(tk.Frame):
    """A compact text widget whose glyph colors form one continuous gradient."""

    def __init__(self, parent, *, text: str, font, background: str) -> None:
        super().__init__(parent, background=background, borderwidth=0, highlightthickness=0)
        count = max(1, len(text) - 1)
        segments = len(GRADIENT_TEXT_COLORS) - 1
        colors = [
            tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
            for color in GRADIENT_TEXT_COLORS
        ]
        for index, char in enumerate(text):
            position = index / count * segments
            segment = min(int(position), segments - 1)
            amount = position - segment
            left, right = colors[segment], colors[segment + 1]
            rgb = tuple(
                round(left[channel] + (right[channel] - left[channel]) * amount)
                for channel in range(3)
            )
            color = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
            tk.Label(
                self,
                text=char,
                font=font,
                background=background,
                foreground=color,
                borderwidth=0,
                padx=0,
                pady=0,
            ).pack(side="left")


class RoundedButton(tk.Canvas):
    """A compact, keyboard-accessible Tk button with a subtle corner radius."""

    def __init__(
        self,
        parent,
        *,
        text: str,
        command,
        width: int,
        canvas_bg: str,
        primary: bool = False,
        height: int = 30,
        radius: int = 8,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            background=canvas_bg,
            highlightthickness=0,
            borderwidth=0,
            takefocus=True,
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.button_width = width
        self.button_height = height
        self.radius = radius
        self.primary = primary
        self.state = "normal"
        self.hovered = False
        self.pressed = False
        self.focused = False
        family = getattr(self._root(), "FONT_FAMILY", "Microsoft YaHei UI")
        self.font = tkfont.Font(family=family, size=9, weight="bold" if primary else "normal")
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        self.bind("<Return>", self._keyboard_activate)
        self.bind("<space>", self._keyboard_activate)
        self._draw()

    def _rounded_rectangle(self, x1, y1, x2, y2, radius, **kwargs) -> None:
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _draw(self) -> None:
        self.delete("all")
        theme = self._root()
        if self.state == "disabled":
            fill, foreground, border = theme.ACTION_SOFT, theme.MUTED, theme.BORDER
        elif self.primary:
            fill = theme.ACTIVE if self.pressed else theme.ACTION_HOVER if self.hovered else theme.ACTION
            foreground, border = "#FFFFFF", fill
        else:
            fill = theme.BORDER if self.pressed else theme.ACTION_SOFT if self.hovered else theme.SURFACE
            foreground, border = getattr(theme, "TEXT_BODY", theme.INK), theme.BORDER
        inset = 2
        outline = theme.ACTION if self.focused and self.state != "disabled" else border
        self._rounded_rectangle(
            inset,
            inset,
            self.button_width - inset,
            self.button_height - inset,
            self.radius,
            fill=fill,
            outline=outline,
            width=2 if self.focused else 1,
        )
        self.create_text(
            self.button_width / 2,
            self.button_height / 2,
            text=self.text,
            fill=foreground,
            font=self.font,
        )
        super().configure(cursor="arrow" if self.state == "disabled" else "hand2")

    def configure(self, cnf=None, **kwargs):
        options = dict(cnf or {})
        options.update(kwargs)
        if "state" in options:
            self.state = options.pop("state")
        if "text" in options:
            self.text = options.pop("text")
        result = super().configure(**options) if options else None
        self._draw()
        return result

    config = configure

    def _enter(self, _event) -> None:
        self.hovered = True
        self._draw()

    def _leave(self, _event) -> None:
        self.hovered = False
        self.pressed = False
        self._draw()

    def _press(self, _event) -> None:
        if self.state != "disabled":
            self.focus_set()
            self.pressed = True
            self._draw()

    def _release(self, event) -> None:
        was_pressed = self.pressed
        self.pressed = False
        self._draw()
        if (
            was_pressed
            and self.state != "disabled"
            and 0 <= event.x <= self.button_width
            and 0 <= event.y <= self.button_height
        ):
            self.command()

    def _focus_in(self, _event) -> None:
        self.focused = True
        self._draw()

    def _focus_out(self, _event) -> None:
        self.focused = False
        self.pressed = False
        self._draw()

    def _keyboard_activate(self, _event) -> str:
        if self.state != "disabled":
            self.command()
        return "break"


class ModeToggle(tk.Canvas):
    """Two-state compact selector with a dark active segment."""

    def __init__(self, parent, *, variable, command, canvas_bg: str) -> None:
        super().__init__(
            parent,
            width=190,
            height=30,
            background=canvas_bg,
            highlightthickness=0,
            borderwidth=0,
            takefocus=True,
            cursor="hand2",
        )
        self.variable = variable
        self.command = command
        self.state = "normal"
        self.focused = False
        self.bind("<Button-1>", self._click)
        self.bind("<Left>", lambda _event: self._select(0.0))
        self.bind("<Right>", lambda _event: self._select(1.0))
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        self._draw()

    def _rounded_rectangle(self, x1, y1, x2, y2, radius, **kwargs) -> None:
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _draw(self) -> None:
        self.delete("all")
        theme = self._root()
        active_right = self.variable.get() >= 0.5
        outline = theme.ACTION if self.focused else theme.BORDER
        self._rounded_rectangle(
            1, 1, 189, 29, 8,
            fill=theme.ACTION_SOFT,
            outline=outline,
            width=2 if self.focused else 1,
        )
        x1, x2 = (96, 187) if active_right else (3, 94)
        active_fill = theme.ACTIVE if self.state != "disabled" else theme.MUTED
        self._rounded_rectangle(x1, 3, x2, 27, 6, fill=active_fill, outline=active_fill)
        family = getattr(theme, "FONT_FAMILY", "Microsoft YaHei UI")
        self.create_text(
            48,
            15,
            text="替换原文件",
            fill="#FFFFFF" if not active_right else getattr(theme, "TEXT_BODY", theme.INK),
            font=(family, 9, "bold" if not active_right else "normal"),
        )
        self.create_text(
            142,
            15,
            text="保留源文件",
            fill="#FFFFFF" if active_right else getattr(theme, "TEXT_BODY", theme.INK),
            font=(family, 9, "bold" if active_right else "normal"),
        )
        super().configure(cursor="arrow" if self.state == "disabled" else "hand2")

    def _select(self, value: float) -> str:
        if self.state != "disabled":
            self.variable.set(value)
            self.command(str(value))
            self._draw()
        return "break"

    def _click(self, event) -> None:
        self.focus_set()
        self._select(0.0 if event.x < 95 else 1.0)

    def _toggle(self, _event=None) -> str:
        return self._select(0.0 if self.variable.get() >= 0.5 else 1.0)

    def _focus_in(self, _event) -> None:
        self.focused = True
        self._draw()

    def _focus_out(self, _event) -> None:
        self.focused = False
        self._draw()

    def configure(self, cnf=None, **kwargs):
        options = dict(cnf or {})
        options.update(kwargs)
        if "state" in options:
            self.state = options.pop("state")
        result = super().configure(**options) if options else None
        self._draw()
        return result

    config = configure


class App(TkinterDnD.Tk):
    CANVAS = "#EAF7FD"
    SURFACE = "#F6FCFF"
    INK = "#1D3748"
    MUTED = "#5C7687"
    BORDER = "#69B7DF"
    ACTION = "#2F9FDC"
    ACTION_HOVER = "#2589C0"
    ACTION_SOFT = "#D8EEF9"
    ACTIVE = "#274C63"
    THEME_RAINBOW = ("#FF892F", "#FF3091", "#9E4BFF", "#46C4FF")
    SUCCESS = "#167A3A"
    WARNING = "#9A6700"

    def __init__(self) -> None:
        super().__init__()
        if os.name == "nt":
            try:
                dpi = ctypes.windll.user32.GetDpiForWindow(self.winfo_id())
                self.tk.call("tk", "scaling", max(1.0, dpi / 72.0))
            except (AttributeError, OSError, tk.TclError):
                pass
        self.title("blues19-亚马逊 AI 人物图片标签工具 · 拾玖Blues")
        self.geometry("760x720")
        self.minsize(720, 580)
        saved_settings = self._load_settings()
        theme_id = saved_settings.get("theme", "RainbowText")
        if theme_id not in THEMES:
            theme_id = "RainbowText"
        self.theme_name = tk.StringVar(value=theme_id)
        saved_font = saved_settings.get("font_family", "Microsoft YaHei UI")
        self.font_family = tk.StringVar(
            value=saved_font if saved_font in FONT_OPTIONS else "Microsoft YaHei UI"
        )
        saved_accent = saved_settings.get("accent_text", "深墨色")
        if saved_settings.get("text_color_version", 1) < 2:
            saved_accent = "深墨色"
        self.accent_text = tk.StringVar(
            value=saved_accent if saved_accent in ACCENT_TEXT_OPTIONS else "七彩渐变"
        )
        self.FONT_FAMILY = self.font_family.get()
        self.bubble_enabled = tk.BooleanVar(value=bool(saved_settings.get("bubble_enabled", True)))
        self._apply_theme_tokens(theme_id)
        self._apply_text_tokens()
        self.configure(background=self.CANVAS)
        self.folder = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.status = tk.StringVar(value="就绪 · 请拖入图片或文件夹")
        self.result_count = tk.StringVar(value="尚未扫描")
        self.suffix = tk.StringVar(value=DEFAULT_SUFFIX)
        self.mode_value = tk.DoubleVar(value=1.0)
        self.mode_text = tk.StringVar(value="保留源文件，生成带尾缀副本")
        self.open_output_dir = tk.BooleanVar(value=True)
        self.view_mode = tk.StringVar(value="list")
        self.thumb_size = tk.IntVar(value=96)
        self.loaded_paths: list[Path] = []
        self.result_paths: list[Path] = []
        self.tag_status: dict[Path, bool | None] = {}
        self.photo_refs: list[ImageTk.PhotoImage] = []
        self.action_buttons: list[tk.Widget] = []
        self.workflow_badges: list[tk.Label] = []
        self.copy_button: RoundedButton | None = None
        self.result_tree: ttk.Treeview | None = None
        self.busy = False
        self.task_queue: Queue[tuple[str, object]] = Queue()
        self.thumb_after_id: str | None = None
        self.settings_expanded = False
        self._configure_style()
        self._build_ui()
        self._apply_gradient_labels(self)
        self.attributes("-alpha", 0.992)
        self.after_idle(self._apply_window_material)
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<DropEnter>>", self.on_drop_enter)
        self.dnd_bind("<<Drop>>", self.on_drop)
        self.result_host.drop_target_register(DND_FILES)
        self.result_host.dnd_bind("<<DropEnter>>", self.on_drop_enter)
        self.result_host.dnd_bind("<<Drop>>", self.on_drop)
        self._build_drop_bubble()
        if not self.bubble_enabled.get():
            self.drop_bubble.withdraw()
        self.bind("<Control-c>", lambda _event: self.copy_paths())
        self.bind("<Escape>", lambda _event: self.focus_set())

    def _load_settings(self) -> dict:
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_settings(self) -> None:
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(
                    {
                        "theme": self.theme_name.get(),
                        "font_family": self.font_family.get(),
                        "accent_text": self.accent_text.get(),
                        "text_color_version": 2,
                        "bubble_enabled": self.bubble_enabled.get(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _apply_theme_tokens(self, theme_id: str) -> None:
        theme = THEMES[theme_id]
        self.CANVAS = theme["canvas"]
        self.SURFACE = theme["surface"]
        self.INK = theme["ink"]
        self.MUTED = theme["muted"]
        self.BORDER = theme["border"]
        self.ACTION = theme["action"]
        self.ACTION_HOVER = theme["hover"]
        self.ACTION_SOFT = theme["soft"]
        self.ACTIVE = theme["active"]
        self.THEME_RAINBOW = theme["rainbow"]

    def _apply_text_tokens(self) -> None:
        mode = self.accent_text.get()
        if mode == "七彩渐变":
            if self.theme_name.get() == "NeonBlue":
                self.TEXT_HEADER = "#FF9566"
                self.TEXT_SECTION = "#F06CC7"
                self.TEXT_BODY = "#C48AFF"
                self.TEXT_MUTED = "#73BFFF"
            else:
                self.TEXT_HEADER = "#D84D63"
                self.TEXT_SECTION = "#A847B8"
                self.TEXT_BODY = "#7047C7"
                self.TEXT_MUTED = "#347FB8"
        else:
            color = {
                "主题色": self.ACTION,
                "深墨色": self.INK,
                "柔和灰": self.MUTED,
            }.get(mode, self.INK)
            self.TEXT_HEADER = color
            self.TEXT_SECTION = color
            self.TEXT_BODY = color
            self.TEXT_MUTED = color

    def _apply_window_material(self) -> None:
        apply_windows_glass(
            self,
            caption_color=self.CANVAS,
            text_color=self.INK,
            border_color=self.BORDER,
            dark=self.theme_name.get() == "NeonBlue",
        )

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=(self.FONT_FAMILY, 10), background=self.CANVAS, foreground=self.TEXT_BODY)
        style.configure("TFrame", background=self.CANVAS)
        style.configure("Surface.TFrame", background=self.SURFACE)
        style.configure(
            "Card.TFrame",
            background=self.SURFACE,
            bordercolor=self.BORDER,
            borderwidth=1,
            relief="solid",
        )
        style.configure("TLabel", background=self.CANVAS, foreground=self.TEXT_BODY)
        style.configure("Surface.TLabel", background=self.SURFACE, foreground=self.TEXT_BODY)
        style.configure("Eyebrow.TLabel", font=(self.FONT_FAMILY, 9, "bold"), foreground=self.TEXT_HEADER)
        style.configure("Header.TLabel", font=(self.FONT_FAMILY, 17, "bold"), foreground=self.TEXT_HEADER)
        style.configure(
            "Section.TLabel",
            background=self.SURFACE,
            font=(self.FONT_FAMILY, 11, "bold"),
            foreground=self.TEXT_SECTION,
        )
        style.configure("Muted.TLabel", foreground=self.TEXT_MUTED)
        style.configure("SurfaceMuted.TLabel", background=self.SURFACE, foreground=self.TEXT_MUTED)
        style.configure("Status.TLabel", foreground=self.TEXT_MUTED, font=(self.FONT_FAMILY, 9))
        style.configure("Count.TLabel", foreground=self.TEXT_SECTION, font=(self.FONT_FAMILY, 10, "bold"))
        style.configure(
            "Tag.TLabel",
            background=self.ACTION_SOFT,
            foreground=self.TEXT_BODY,
            font=(self.FONT_FAMILY, 9),
            padding=(8, 3),
        )
        style.configure(
            "TEntry",
            fieldbackground=self.SURFACE,
            foreground=self.TEXT_BODY,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            focuscolor=self.ACTION,
            padding=8,
        )
        style.configure(
            "TButton",
            background=self.SURFACE,
            foreground=self.TEXT_BODY,
            bordercolor=self.BORDER,
            focuscolor=self.ACTION,
            padding=(13, 8),
        )
        style.map(
            "TButton",
            background=[("active", self.ACTION_SOFT), ("pressed", self.BORDER), ("disabled", self.ACTION_SOFT)],
            foreground=[("disabled", self.MUTED)],
        )
        style.configure(
            "Primary.TButton",
            background=self.ACTION,
            foreground="#FFFFFF",
            bordercolor=self.ACTION,
            focuscolor=self.INK,
            padding=(16, 9),
        )
        style.map(
            "Primary.TButton",
            background=[("active", self.ACTION_HOVER), ("pressed", "#074D9F"), ("disabled", "#9CBDE5")],
            foreground=[("disabled", "#F5F7FA")],
        )
        style.configure("TRadiobutton", background=self.CANVAS, foreground=self.TEXT_BODY, focuscolor=self.ACTION)
        style.configure(
            "Surface.TRadiobutton",
            background=self.SURFACE,
            foreground=self.TEXT_BODY,
            focuscolor=self.ACTION,
        )
        style.configure(
            "Surface.TCheckbutton",
            background=self.SURFACE,
            foreground=self.TEXT_BODY,
            focuscolor=self.ACTION,
        )
        style.configure(
            "Horizontal.TScale",
            background=self.SURFACE,
            troughcolor=self.ACTION_SOFT,
            bordercolor=self.SURFACE,
            sliderlength=22,
        )
        style.configure(
            "Treeview",
            background=self.SURFACE,
            fieldbackground=self.SURFACE,
            foreground=self.TEXT_BODY,
            bordercolor=self.BORDER,
            rowheight=112,
        )
        style.configure(
            "Treeview.Heading",
            background=self.ACTION_SOFT,
            foreground=self.TEXT_SECTION,
            bordercolor=self.BORDER,
            font=(self.FONT_FAMILY, 9, "bold"),
            padding=(8, 7),
        )
        style.map(
            "Treeview",
            background=[("selected", self.ACTION_SOFT)],
            foreground=[("selected", self.TEXT_BODY)],
        )
        style.configure(
            "Blue.Horizontal.TProgressbar",
            background=self.ACTION,
            troughcolor=self.ACTION_SOFT,
            bordercolor=self.CANVAS,
            lightcolor=self.ACTION,
            darkcolor=self.ACTION,
        )
        style.configure(
            "Glass.Vertical.TScrollbar",
            background=self.ACTION_SOFT,
            troughcolor=self.SURFACE,
            bordercolor=self.BORDER,
            arrowcolor=self.MUTED,
            lightcolor=self.ACTION_SOFT,
            darkcolor=self.ACTION_SOFT,
            relief="flat",
            borderwidth=0,
            arrowsize=12,
        )
        style.map(
            "Glass.Vertical.TScrollbar",
            background=[("active", self.BORDER), ("pressed", self.ACTION)],
            arrowcolor=[("active", self.INK)],
        )
        style.configure(
            "Glass.TCombobox",
            fieldbackground=self.ACTION_SOFT,
            background=self.ACTION_SOFT,
            foreground=self.TEXT_BODY,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            arrowcolor=self.TEXT_BODY,
            padding=(8, 6),
        )
        style.map(
            "Glass.TCombobox",
            fieldbackground=[("readonly", self.ACTION_SOFT)],
            foreground=[("readonly", self.TEXT_BODY)],
            background=[("readonly", self.ACTION_SOFT), ("active", self.BORDER)],
            arrowcolor=[("active", self.ACTION)],
            selectbackground=[("readonly", self.ACTION_SOFT)],
            selectforeground=[("readonly", self.TEXT_BODY)],
        )
        self.option_add("*TCombobox*Listbox.background", self.SURFACE)
        self.option_add("*TCombobox*Listbox.foreground", self.TEXT_BODY)
        self.option_add("*TCombobox*Listbox.selectBackground", self.ACTION)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

    def _build_drop_bubble(self) -> None:
        size = 88
        transparent = "#071D2A"
        bubble = tk.Toplevel(self)
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.attributes("-alpha", 1.0)
        try:
            bubble.attributes("-transparentcolor", transparent)
        except tk.TclError:
            pass
        x = max(12, bubble.winfo_screenwidth() - size - 28)
        y = max(12, bubble.winfo_screenheight() // 3)
        bubble.geometry(f"{size}x{size}+{x}+{y}")
        bubble.configure(background=transparent)

        canvas = tk.Canvas(
            bubble,
            width=size,
            height=size,
            background=transparent,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )
        canvas.pack(fill="both", expand=True)
        scale = 4
        high_size = size * scale
        artwork = Image.new("RGBA", (high_size, high_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(artwork)
        draw.ellipse(
            (2 * scale, 2 * scale, high_size - 2 * scale, high_size - 2 * scale),
            fill=self.ACTION_SOFT,
            outline=self.ACTION,
            width=2 * scale,
        )
        draw.ellipse(
            (5 * scale, 5 * scale, high_size - 5 * scale, high_size - 5 * scale),
            fill=self.ACTIVE,
            outline="#67D9F5",
            width=2 * scale,
        )
        center = high_size / 2
        for index in range(24):
            angle = math.radians(index * 15)
            outer_radius = 39 * scale
            inner_radius = (35 if index % 3 else 33) * scale
            x1 = center + math.cos(angle) * inner_radius
            y1 = center + math.sin(angle) * inner_radius
            x2 = center + math.cos(angle) * outer_radius
            y2 = center + math.sin(angle) * outer_radius
            draw.line((x1, y1, x2, y2), fill=self.ACTION, width=1 * scale)
        inner = 13 * scale
        draw.ellipse(
            (inner, inner, high_size - inner, high_size - inner),
            fill="#071D2B",
            outline="#7DE8FF",
            width=2 * scale,
        )
        draw.line((center, 16 * scale, center, 21 * scale), fill="#7DE8FF", width=1 * scale)
        draw.line((center, 67 * scale, center, 72 * scale), fill="#7DE8FF", width=1 * scale)
        draw.line((16 * scale, center, 21 * scale, center), fill="#7DE8FF", width=1 * scale)
        draw.line((67 * scale, center, 72 * scale, center), fill="#7DE8FF", width=1 * scale)
        font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyhbd.ttc"
        try:
            bubble_font = ImageFont.truetype(str(font_path), 9 * scale)
        except OSError:
            bubble_font = ImageFont.load_default()
        draw.text(
            (high_size / 2, 34 * scale),
            "拖入图片",
            fill="#FFFFFF",
            font=bubble_font,
            anchor="mm",
        )
        draw.text(
            (high_size / 2, 53 * scale),
            "写入 AI 标签",
            fill="#62D9FF",
            font=bubble_font,
            anchor="mm",
        )
        artwork = artwork.resize((size, size), Image.Resampling.LANCZOS)
        # Tk's color-key transparency exposes the canvas color through partially
        # transparent antialias pixels. Flatten against the exact key color with
        # a binary mask so Tk never gets a chance to blend a magenta halo.
        alpha = artwork.getchannel("A").point(lambda value: 255 if value >= 96 else 0)
        keyed_artwork = Image.new("RGB", (size, size), transparent)
        keyed_artwork.paste(artwork.convert("RGB"), mask=alpha)
        artwork = keyed_artwork
        bubble_photo = ImageTk.PhotoImage(artwork)
        canvas.create_image(size / 2, size / 2, image=bubble_photo)
        self.drop_bubble_photo = bubble_photo
        self.drop_bubble_canvas = canvas

        bubble.drop_target_register(DND_FILES)
        bubble.dnd_bind("<<DropEnter>>", self.on_drop_enter)
        bubble.dnd_bind("<<Drop>>", self.on_bubble_drop)
        canvas.drop_target_register(DND_FILES)
        canvas.dnd_bind("<<DropEnter>>", self.on_drop_enter)
        canvas.dnd_bind("<<Drop>>", self.on_bubble_drop)
        drag_state = {"offset_x": 0, "offset_y": 0, "last_x": x, "last_y": y}

        def start_drag(event) -> None:
            drag_state["offset_x"] = event.x_root - bubble.winfo_x()
            drag_state["offset_y"] = event.y_root - bubble.winfo_y()
            drag_state["last_x"] = bubble.winfo_x()
            drag_state["last_y"] = bubble.winfo_y()
            bubble.attributes("-alpha", 1.0)

        def move_bubble(event) -> None:
            target_x = event.x_root - drag_state["offset_x"]
            target_y = event.y_root - drag_state["offset_y"]
            if abs(target_x - drag_state["last_x"]) < 2 and abs(target_y - drag_state["last_y"]) < 2:
                return
            drag_state["last_x"] = target_x
            drag_state["last_y"] = target_y
            bubble.geometry(f"+{target_x}+{target_y}")

        def finish_drag(_event) -> None:
            bubble.attributes("-alpha", 1.0)

        def show_main(_event=None) -> None:
            self.deiconify()
            self.lift()
            self.focus_force()

        canvas.bind("<ButtonPress-1>", start_drag)
        canvas.bind("<B1-Motion>", move_bubble)
        canvas.bind("<ButtonRelease-1>", finish_drag)
        canvas.bind("<Double-Button-1>", show_main)
        canvas.bind("<Button-3>", show_main)
        self.drop_bubble = bubble

    def open_settings(self) -> None:
        if self.settings_expanded:
            if hasattr(self, "settings_panel") and self.settings_panel.winfo_exists():
                self.settings_panel.destroy()
            self.settings_expanded = False
            self.geometry(f"760x{self.winfo_height()}+{self.winfo_x()}+{self.winfo_y()}")
            return
        self._show_settings_panel()

    def _show_settings_panel(self) -> None:
        settings_width = 356
        height = max(self.winfo_height(), 580)
        x = self.winfo_x()
        y = self.winfo_y()
        expanded_width = 760 + settings_width
        if x + expanded_width > self.winfo_screenwidth():
            x = max(0, self.winfo_screenwidth() - expanded_width)
        self.geometry(f"{expanded_width}x{height}+{x}+{y}")
        self.settings_expanded = True

        panel = ttk.Frame(self, style="Card.TFrame", padding=(18, 18))
        panel.place(x=770, y=18, width=settings_width - 20, relheight=1, height=-36)
        self.settings_panel = panel
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(13, weight=1)
        ttk.Label(panel, text="外观设置", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(panel, text="选择主题与悬浮窗显示方式", style="SurfaceMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(3, 18)
        )
        ttk.Label(panel, text="界面主题", style="Section.TLabel").grid(
            row=2, column=0, sticky="w", pady=(0, 8)
        )
        theme_row = ttk.Frame(panel, style="Surface.TFrame")
        theme_row.grid(row=3, column=0, sticky="ew")
        for index, (theme_id, theme) in enumerate(THEMES.items()):
            option = tk.Radiobutton(
                theme_row,
                text=theme["name"],
                value=theme_id,
                variable=self.theme_name,
                command=lambda value=theme_id: self.change_theme(value),
                indicatoron=False,
                bg=self.SURFACE,
                fg=self.TEXT_BODY,
                selectcolor=self.ACTION,
                activebackground=self.ACTION_SOFT,
                activeforeground=self.TEXT_BODY,
                font=(self.FONT_FAMILY, 9),
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                padx=10,
                pady=7,
                cursor="hand2",
            )
            option.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=(0, 6))
            theme_row.columnconfigure(index % 2, weight=1)

        ttk.Separator(panel, orient="horizontal").grid(
            row=4, column=0, sticky="ew", pady=(14, 16)
        )
        ttk.Label(panel, text="字体", style="Section.TLabel").grid(
            row=5, column=0, sticky="w", pady=(0, 8)
        )
        font_box = ttk.Combobox(
            panel,
            textvariable=self.font_family,
            values=FONT_OPTIONS,
            state="readonly",
            style="Glass.TCombobox",
        )
        font_box.grid(row=6, column=0, sticky="ew")
        font_box.bind("<<ComboboxSelected>>", self.on_appearance_change)
        ttk.Label(panel, text="强调文字颜色", style="SurfaceMuted.TLabel").grid(
            row=7, column=0, sticky="w", pady=(12, 5)
        )
        accent_box = ttk.Combobox(
            panel,
            textvariable=self.accent_text,
            values=ACCENT_TEXT_OPTIONS,
            state="readonly",
            style="Glass.TCombobox",
        )
        accent_box.grid(row=8, column=0, sticky="ew")
        accent_box.bind("<<ComboboxSelected>>", self.on_appearance_change)
        ttk.Separator(panel, orient="horizontal").grid(
            row=9, column=0, sticky="ew", pady=(18, 16)
        )
        ttk.Label(panel, text="悬浮窗", style="Section.TLabel").grid(
            row=10, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Checkbutton(
            panel,
            text="启用悬浮窗",
            variable=self.bubble_enabled,
            command=self.on_bubble_enabled,
            style="Surface.TCheckbutton",
        ).grid(row=11, column=0, sticky="w")
        ttk.Label(
            panel,
            text="拖入图片后会直接写入标签，成功时显示绿色灯效。",
            style="SurfaceMuted.TLabel",
            wraplength=290,
        ).grid(row=12, column=0, sticky="w", pady=(14, 0))

        brand = ttk.Frame(panel, style="Surface.TFrame")
        brand.grid(row=14, column=0, sticky="ew", pady=(18, 0))
        logo_path = RESOURCE_DIR / "blues19-brand-logo.png"
        try:
            with Image.open(logo_path) as source_logo:
                logo = source_logo.convert("RGBA").resize((76, 76), Image.Resampling.LANCZOS)
            mask = Image.new("L", logo.size, 0)
            ImageDraw.Draw(mask).ellipse((1, 1, 74, 74), fill=255)
            logo.putalpha(mask)
            self.brand_logo_photo = ImageTk.PhotoImage(logo)
            ttk.Label(brand, image=self.brand_logo_photo, style="Surface.TLabel").pack(
                side="left", padx=(0, 12)
            )
        except OSError:
            pass
        brand_copy = ttk.Frame(brand, style="Surface.TFrame")
        brand_copy.pack(side="left", fill="x", expand=True)
        GradientText(
            brand_copy,
            text="拾玖说跨境AI",
            font=(self.FONT_FAMILY, 11, "bold"),
            background=self.SURFACE,
        ).pack(anchor="w")
        ttk.Label(brand_copy, text="微信公众号", style="SurfaceMuted.TLabel").pack(
            anchor="w", pady=(4, 0)
        )
        GradientText(
            brand_copy,
            text="作者 · 拾玖Blues",
            font=(self.FONT_FAMILY, 9),
            background=self.SURFACE,
        ).pack(anchor="w", pady=(2, 0))
        self._apply_gradient_labels(panel)

    def change_theme(self, theme_id: str) -> None:
        if theme_id not in THEMES:
            return
        self.theme_name.set(theme_id)
        self._apply_theme_tokens(theme_id)
        self._apply_text_tokens()
        self._save_settings()
        self.after_idle(self._rebuild_themed_ui)

    def on_appearance_change(self, _event=None) -> None:
        self.FONT_FAMILY = self.font_family.get()
        self._apply_text_tokens()
        self._save_settings()
        self.after_idle(self._rebuild_themed_ui)

    def _apply_gradient_labels(self, container: tk.Misc) -> None:
        if self.accent_text.get() != "七彩渐变":
            return
        style_engine = ttk.Style(self)
        for child in list(container.winfo_children()):
            if isinstance(child, ttk.Label):
                if child is getattr(self, "size_label", None):
                    continue
                if child.cget("image") or child.cget("textvariable"):
                    continue
                text = str(child.cget("text"))
                if not text.strip():
                    continue
                style_name = child.cget("style") or "TLabel"
                font_spec = style_engine.lookup(style_name, "font") or (self.FONT_FAMILY, 10)
                background = style_engine.lookup(style_name, "background") or self.CANVAS
                manager = child.winfo_manager()
                replacement = GradientText(
                    child.master,
                    text=text,
                    font=font_spec,
                    background=background,
                )
                if manager == "grid":
                    options = child.grid_info()
                    options.pop("in", None)
                    replacement.grid(**options)
                elif manager == "pack":
                    options = child.pack_info()
                    options.pop("in", None)
                    options.pop("before", None)
                    options.pop("after", None)
                    replacement.pack(before=child, **options)
                elif manager == "place":
                    options = child.place_info()
                    options.pop("in", None)
                    replacement.place(**options)
                else:
                    replacement.destroy()
                    continue
                child.destroy()
            else:
                self._apply_gradient_labels(child)

    def _rebuild_themed_ui(self) -> None:
        was_expanded = self.settings_expanded
        for child in list(self.winfo_children()):
            child.destroy()
        self.settings_expanded = False
        self.action_buttons = []
        self.workflow_badges = []
        self.copy_button = None
        self.result_tree = None
        self.configure(background=self.CANVAS)
        self._configure_style()
        self._build_ui()
        self._apply_gradient_labels(self)
        self.result_host.drop_target_register(DND_FILES)
        self.result_host.dnd_bind("<<DropEnter>>", self.on_drop_enter)
        self.result_host.dnd_bind("<<Drop>>", self.on_drop)
        self._build_drop_bubble()
        if not self.bubble_enabled.get():
            self.drop_bubble.withdraw()
        if was_expanded:
            self._show_settings_panel()
        self.after_idle(self._apply_window_material)

    def on_bubble_enabled(self) -> None:
        if self.bubble_enabled.get():
            self.drop_bubble.deiconify()
            self.drop_bubble.lift()
        else:
            self.drop_bubble.withdraw()
        self._save_settings()

    def _gradient_text_photo(self, text: str) -> ImageTk.PhotoImage:
        scale = 3
        width, height = 184 * scale, 24 * scale
        font_files = {
            "Microsoft YaHei UI": "msyhbd.ttc",
            "Microsoft YaHei": "msyhbd.ttc",
            "SimHei": "simhei.ttf",
        }
        font_path = (
            Path(os.environ.get("WINDIR", r"C:\Windows"))
            / "Fonts"
            / font_files.get(self.FONT_FAMILY, "msyhbd.ttc")
        )
        try:
            font = ImageFont.truetype(str(font_path), 10 * scale)
        except OSError:
            font = ImageFont.load_default()
        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        bbox = mask_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        origin = ((width - text_width) // 2, (height - text_height) // 2 - bbox[1])
        mask_draw.text(origin, text, fill=255, font=font)

        accent_mode = self.accent_text.get()
        if accent_mode == "主题色":
            stops = (self.ACTION, self.ACTION)
        elif accent_mode == "深墨色":
            stops = (self.INK, self.INK)
        elif accent_mode == "柔和灰":
            stops = (self.MUTED, self.MUTED)
        else:
            stops = (
                "#FF8A3D",
                "#FF5D68",
                "#FF3E9D",
                "#C54DDB",
                "#895CF2",
                "#4C90E9",
                "#38C6D9",
            )
        gradient = Image.new("RGB", (width, height))
        pixels = gradient.load()
        segments = max(1, len(stops) - 1)
        colors = [tuple(int(color[index : index + 2], 16) for index in (1, 3, 5)) for color in stops]
        for x in range(width):
            text_position = min(1.0, max(0.0, (x - origin[0]) / max(1, text_width)))
            position = text_position * segments
            segment = min(int(position), segments - 1)
            amount = position - segment
            left, right = colors[segment], colors[segment + 1]
            color = tuple(round(left[channel] + (right[channel] - left[channel]) * amount) for channel in range(3))
            for y in range(height):
                pixels[x, y] = color
        background = Image.new("RGB", (width, height), self.CANVAS)
        background.paste(gradient, mask=mask)
        rendered = background.resize((width // scale, height // scale), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(rendered)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=(14, 8, 14, 6))
        root.place(x=0, y=0, width=760, relheight=1)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="AI 人物图片标签", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        settings_button = tk.Button(
            header,
            text="\uE713",
            command=self.open_settings,
            bg=self.CANVAS,
            fg=self.TEXT_BODY,
            activebackground=self.ACTION_SOFT,
            activeforeground=self.TEXT_BODY,
            relief="flat",
            borderwidth=0,
            font=("Segoe MDL2 Assets", 11),
            cursor="hand2",
            takefocus=True,
            width=2,
        )
        settings_button.grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Label(
            header,
            text=f"写入标签：XMP dc:subject = {TAG}",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(1, 0))

        controls = ttk.Frame(root, style="Card.TFrame", padding=(9, 5))
        controls.grid(row=1, column=0, sticky="ew", pady=(6, 5))
        controls.columnconfigure(2, weight=1)
        ttk.Label(controls, text="尾缀", style="SurfaceMuted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(controls, textvariable=self.suffix, width=13).grid(
            row=0, column=1, sticky="w", padx=(6, 14)
        )
        mode_toggle = ModeToggle(
            controls,
            variable=self.mode_value,
            command=self.on_mode_change,
            canvas_bg=self.SURFACE,
        )
        mode_toggle.grid(row=0, column=3, padx=(8, 12))
        self.action_buttons.append(mode_toggle)

        ttk.Checkbutton(
            controls,
            text="完成后打开目录",
            variable=self.open_output_dir,
            style="Surface.TCheckbutton",
        ).grid(row=0, column=4, padx=(0, 10))

        write_button = RoundedButton(
            controls,
            text="写入标签",
            command=self.write_loaded,
            width=88,
            canvas_bg=self.SURFACE,
            primary=True,
        )
        write_button.grid(row=0, column=5, padx=(0, 5))
        clear_button = RoundedButton(
            controls,
            text="清除标签",
            command=self.clear_loaded,
            width=88,
            canvas_bg=self.SURFACE,
        )
        clear_button.grid(row=0, column=6, padx=(0, 5))
        self.action_buttons.extend((write_button, clear_button))

        result_section = ttk.Frame(root, style="Card.TFrame", padding=(9, 7))
        result_section.grid(row=2, column=0, sticky="nsew")
        result_section.columnconfigure(0, weight=1)
        result_section.rowconfigure(1, weight=1)

        result_toolbar = ttk.Frame(result_section, style="Surface.TFrame")
        result_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(result_toolbar, text="图片清单", style="Section.TLabel").pack(side="left")
        ttk.Label(result_toolbar, textvariable=self.result_count, style="SurfaceMuted.TLabel").pack(
            side="left", padx=(8, 0)
        )
        copy_button = RoundedButton(
            result_toolbar,
            text="复制路径",
            command=self.copy_paths,
            width=84,
            canvas_bg=self.SURFACE,
        )
        copy_button.pack(side="right")
        self.copy_button = copy_button
        self.action_buttons.append(copy_button)
        self.size_label = ttk.Label(result_toolbar, text="96 px", style="SurfaceMuted.TLabel")
        self.size_label.pack(side="right", padx=(6, 4))
        ttk.Scale(
            result_toolbar,
            from_=64,
            to=180,
            variable=self.thumb_size,
            command=self.on_thumb_change,
            length=130,
        ).pack(side="right", padx=(6, 0))
        ttk.Label(result_toolbar, text="缩略图", style="SurfaceMuted.TLabel").pack(
            side="right", padx=(12, 0)
        )
        ttk.Radiobutton(
            result_toolbar,
            text="平铺",
            value="grid",
            variable=self.view_mode,
            command=self.render_results,
            style="Surface.TRadiobutton",
        ).pack(side="right", padx=(6, 0))
        ttk.Radiobutton(
            result_toolbar,
            text="列表",
            value="list",
            variable=self.view_mode,
            command=self.render_results,
            style="Surface.TRadiobutton",
        ).pack(side="right", padx=(14, 0))

        self.result_host = ttk.Frame(result_section, style="Surface.TFrame")
        self.result_host.grid(row=1, column=0, sticky="nsew")

        footer = ttk.Frame(root)
        footer.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status, style="Status.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.progress = ttk.Progressbar(
            footer,
            mode="indeterminate",
            length=150,
            style="Blue.Horizontal.TProgressbar",
        )
        self.progress.grid(row=0, column=1, sticky="e")
        self.progress.grid_remove()
        self.render_results()

    def _build_legacy_ui(self) -> None:
        root = ttk.Frame(self, padding=(14, 6, 14, 6))
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)
        ttk.Label(header, text="BLUES19 · METADATA UTILITY", style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, text="AI 人物图片标签", style="Header.TLabel").grid(
            row=0, column=1, sticky="w", padx=(12, 16)
        )
        ttk.Label(
            header,
            text="选择图片、确定输出方式、写入并核验亚马逊要求的 XMP 标签。",
            style="Muted.TLabel",
        ).grid(row=0, column=2, sticky="w")
        ttk.Label(header, text="作者 · 拾玖Blues", style="Muted.TLabel").grid(
            row=0, column=3, sticky="e"
        )

        workflow = ttk.Frame(root, style="Card.TFrame", padding=(9, 4))
        workflow.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        workflow.columnconfigure(1, weight=1)
        workflow.columnconfigure(3, weight=1)
        steps = (
            ("1", "选择目录"),
            ("2", "设置输出"),
            ("3", "写入或扫描"),
        )
        for index, (number, label) in enumerate(steps):
            column = index * 2
            step = ttk.Frame(workflow, style="Surface.TFrame")
            step.grid(row=0, column=column, sticky="w")
            badge = tk.Label(
                step,
                text=number,
                bg=self.ACTION if index == 0 else "#E5E5EA",
                fg="#FFFFFF" if index == 0 else self.MUTED,
                font=("Segoe UI Semibold", 9),
                width=2,
                pady=2,
            )
            badge.grid(row=0, column=0, padx=(0, 7))
            self.workflow_badges.append(badge)
            ttk.Label(step, text=label, style="Surface.TLabel").grid(row=0, column=1, sticky="w")
            if index < 2:
                ttk.Separator(workflow, orient="horizontal").grid(
                    row=0, column=column + 1, sticky="ew", padx=14
                )

        setup = ttk.Frame(root)
        setup.grid(row=2, column=0, sticky="ew")
        setup.columnconfigure(0, weight=3)
        setup.columnconfigure(1, weight=2)

        source_card = ttk.Frame(setup, style="Card.TFrame", padding=(10, 7))
        source_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        source_card.columnconfigure(1, weight=1)
        ttk.Label(source_card, text="图片来源", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            source_card,
            text="可拖入图片/文件夹 · 不进入子文件夹",
            style="SurfaceMuted.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))
        folder_row = ttk.Frame(source_card, style="Surface.TFrame")
        folder_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        folder_row.columnconfigure(0, weight=1)
        ttk.Entry(folder_row, textvariable=self.folder).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        choose_button = RoundedButton(
            folder_row,
            text="选择文件夹  Ctrl+O",
            command=self.choose_folder,
            width=130,
            canvas_bg=self.SURFACE,
        )
        choose_button.grid(row=0, column=1)
        self.action_buttons.append(choose_button)

        output_card = ttk.Frame(setup, style="Card.TFrame", padding=(10, 7))
        output_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        output_card.columnconfigure(2, weight=1)
        ttk.Label(output_card, text="输出方式", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(output_card, text="文件名尾缀", style="SurfaceMuted.TLabel").grid(
            row=0, column=1, sticky="w", padx=(14, 0)
        )
        ttk.Entry(output_card, textvariable=self.suffix, width=16).grid(
            row=0, column=2, sticky="ew", padx=(8, 0)
        )
        ttk.Label(output_card, text="替换原文件", style="SurfaceMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(5, 0)
        )
        mode_slider = ttk.Scale(
            output_card,
            from_=0,
            to=1,
            variable=self.mode_value,
            command=self.on_mode_change,
        )
        mode_slider.grid(row=1, column=1, sticky="ew", padx=8, pady=(5, 0))
        ttk.Label(output_card, text="保留源文件", style="SurfaceMuted.TLabel").grid(
            row=1, column=2, sticky="e", pady=(5, 0)
        )

        tag_strip = ttk.Frame(root, style="Card.TFrame", padding=(9, 5))
        tag_strip.grid(row=3, column=0, sticky="ew", pady=(5, 5))
        tag_strip.columnconfigure(3, weight=1)
        ttk.Label(tag_strip, text="写入标签", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(tag_strip, text="XMP dc:subject", style="Tag.TLabel").grid(
            row=0, column=1, padx=(14, 6)
        )
        ttk.Label(tag_strip, text=TAG, style="Tag.TLabel").grid(row=0, column=2)
        ttk.Label(
            tag_strip,
            text="AI 逼真人物",
            style="SurfaceMuted.TLabel",
        ).grid(row=0, column=3, sticky="w", padx=(8, 8))

        action_bar = ttk.Frame(tag_strip, style="Surface.TFrame")
        action_bar.grid(row=0, column=4, sticky="e")
        primary = RoundedButton(
            action_bar,
            text="写入选定图片",
            command=self.write_selected,
            width=100,
            canvas_bg=self.SURFACE,
            primary=True,
        )
        primary.pack(side="left", padx=(0, 5))
        write_all_button = RoundedButton(
            action_bar,
            text="写入文件夹全部图片",
            command=self.write_all,
            width=120,
            canvas_bg=self.SURFACE,
        )
        write_all_button.pack(side="left", padx=(0, 5))
        scan_button = RoundedButton(
            action_bar,
            text="扫描标签  Ctrl+F",
            command=self.scan,
            width=145,
            canvas_bg=self.SURFACE,
        )
        scan_button.pack(side="left")
        self.action_buttons.extend((primary, write_all_button, scan_button))

        result_section = ttk.Frame(root, style="Card.TFrame", padding=(9, 7))
        result_section.grid(row=4, column=0, sticky="nsew")
        result_section.columnconfigure(0, weight=1)
        result_section.rowconfigure(1, weight=1)

        result_toolbar = ttk.Frame(result_section, style="Surface.TFrame")
        result_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(result_toolbar, text="核验结果", style="Section.TLabel").pack(side="left")
        ttk.Label(result_toolbar, textvariable=self.result_count, style="SurfaceMuted.TLabel").pack(
            side="left", padx=(8, 0)
        )
        copy_button = RoundedButton(
            result_toolbar,
            text="复制路径",
            command=self.copy_paths,
            width=84,
            canvas_bg=self.SURFACE,
        )
        copy_button.pack(side="right")
        self.copy_button = copy_button
        self.action_buttons.append(copy_button)
        self.size_label = ttk.Label(result_toolbar, text="96 px", style="SurfaceMuted.TLabel")
        self.size_label.pack(side="right", padx=(6, 4))
        ttk.Scale(
            result_toolbar,
            from_=64,
            to=180,
            variable=self.thumb_size,
            command=self.on_thumb_change,
            length=150,
        ).pack(side="right", padx=(6, 0))
        ttk.Label(result_toolbar, text="缩略图", style="SurfaceMuted.TLabel").pack(side="right", padx=(12, 0))
        ttk.Radiobutton(
            result_toolbar,
            text="平铺",
            value="grid",
            variable=self.view_mode,
            command=self.render_results,
            style="Surface.TRadiobutton",
        ).pack(side="right", padx=(6, 0))
        ttk.Radiobutton(
            result_toolbar,
            text="列表",
            value="list",
            variable=self.view_mode,
            command=self.render_results,
            style="Surface.TRadiobutton",
        ).pack(side="right", padx=(14, 0))

        self.result_host = ttk.Frame(result_section, style="Surface.TFrame")
        self.result_host.grid(row=1, column=0, sticky="nsew")

        footer = ttk.Frame(root)
        footer.grid(row=5, column=0, sticky="ew", pady=(4, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(
            footer,
            mode="indeterminate",
            length=170,
            style="Blue.Horizontal.TProgressbar",
        )
        self.progress.grid(row=0, column=1, sticky="e")
        self.progress.grid_remove()
        self.render_results()

    def update_workflow(self, active_step: int) -> None:
        for index, badge in enumerate(self.workflow_badges, start=1):
            active = index == active_step
            badge.configure(
                bg=self.ACTION if active else "#E5E5EA",
                fg="#FFFFFF" if active else self.MUTED,
            )

    def refresh_action_states(self) -> None:
        if self.copy_button:
            self.copy_button.configure(
                state="normal" if self.result_paths and not self.busy else "disabled"
            )

    def set_busy(self, busy: bool, message: str = "") -> None:
        self.busy = busy
        for button in self.action_buttons:
            button.configure(state="disabled" if busy else "normal")
        if busy:
            self.update_workflow(3)
            self.status.set(message)
            self.progress.grid()
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()
            self.refresh_action_states()

    def run_background(self, message: str, worker, on_success) -> None:
        if self.busy:
            return
        self.set_busy(True, message)

        def execute() -> None:
            try:
                self.task_queue.put(("success", worker()))
            except Exception as exc:
                self.task_queue.put(("error", exc))

        threading.Thread(target=execute, daemon=True).start()

        def poll() -> None:
            try:
                state, payload = self.task_queue.get_nowait()
            except Empty:
                self.after(80, poll)
                return
            self.set_busy(False)
            if state == "error":
                self.status.set(f"操作失败 · {payload}")
                return
            on_success(payload)

        self.after(80, poll)

    def current_folder(self) -> Path | None:
        folder = Path(self.folder.get().strip())
        if not folder.is_dir():
            self.status.set("文件夹无效 · 请拖入一个存在的图片文件夹")
            return None
        return folder.resolve()

    def on_drop_enter(self, _event) -> str:
        if not self.busy:
            self.status.set("松开即可载入图片或文件夹")
        return "copy"

    def on_drop(self, event) -> str:
        if self.busy:
            self.status.set("正在处理图片，请完成后再拖入")
            return "refuse_drop"

        paths = [Path(item).resolve() for item in self.tk.splitlist(event.data)]
        folders = [path for path in paths if path.is_dir()]
        images = [path for path in paths if path.is_file() and path.suffix.lower() in EXTENSIONS]

        if folders:
            if len(paths) != 1:
                self.status.set("未载入 · 请单独拖入一个文件夹")
                return "copy"
            images = image_files(folders[0])

        if not images:
            self.status.set("未载入 · 拖入的内容不包含支持的图片")
            return "copy"

        self.loaded_paths = list(dict.fromkeys(images))
        self.result_paths = self.loaded_paths.copy()
        self.tag_status = {path: None for path in self.loaded_paths}
        self.render_results()
        self.refresh_tag_status()
        return "copy"

    def on_bubble_drop(self, event) -> str:
        if self.busy:
            self.status.set("正在处理图片，请完成后再拖入")
            return "refuse_drop"

        paths = [Path(item).resolve() for item in self.tk.splitlist(event.data)]
        folders = [path for path in paths if path.is_dir()]
        images = [path for path in paths if path.is_file() and path.suffix.lower() in EXTENSIONS]
        if folders:
            if len(paths) != 1:
                self.status.set("未写入 · 请单独拖入一个文件夹")
                return "copy"
            images = image_files(folders[0])
        if not images:
            self.status.set("未写入 · 拖入的内容不包含支持的图片")
            return "copy"

        unique_images = list(dict.fromkeys(images))
        self.loaded_paths = unique_images
        self.result_paths = unique_images.copy()
        self.tag_status = {path: None for path in unique_images}
        self.render_results()
        self._write(unique_images, on_completed=self.show_bubble_success)
        return "copy"

    def show_bubble_success(self) -> None:
        if not hasattr(self, "drop_bubble_canvas") or not self.drop_bubble_canvas.winfo_exists():
            return
        canvas = self.drop_bubble_canvas
        canvas.delete("success")
        canvas.create_oval(3, 3, 85, 85, outline="#58F08A", width=4, tags="success")
        canvas.create_oval(8, 8, 80, 80, outline="#22B965", width=2, tags="success")
        canvas.create_oval(
            28, 28, 60, 60,
            fill="#092C21",
            outline="#72F59B",
            width=2,
            tags="success",
        )
        canvas.create_text(
            44, 44,
            text="✓",
            fill="#72F59B",
            font=("Segoe UI Symbol", 18, "bold"),
            tags="success",
        )
        self.after(
            2200,
            lambda: canvas.delete("success") if canvas.winfo_exists() else None,
        )

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.folder.get() or str(Path.home()))
        if selected:
            self.folder.set(selected)
            self.result_paths = []
            self.render_results()
            self.update_workflow(2)
            self.status.set("目录已就绪 · 可选择图片写入，或扫描已有标签")

    def on_mode_change(self, _value: str = "") -> None:
        keep = self.mode_value.get() >= 0.5
        self.mode_value.set(1.0 if keep else 0.0)
        self.mode_text.set("保留源文件，生成带尾缀副本" if keep else "写入原文件，并添加尾缀重命名")

    def on_thumb_change(self, _value: str = "") -> None:
        self.size_label.configure(text=f"{int(self.thumb_size.get())} px")
        if self.thumb_after_id:
            self.after_cancel(self.thumb_after_id)
        if self.result_paths:
            self.thumb_after_id = self.after(180, self.render_results)

    def write_loaded(self) -> None:
        if not self.loaded_paths:
            self.status.set("请先把图片或文件夹拖入主窗口或悬浮窗")
            return
        self._write(self.loaded_paths.copy())

    def clear_loaded(self) -> None:
        if not self.loaded_paths:
            self.status.set("请先拖入需要清除标签的图片")
            return
        paths = self.loaded_paths.copy()

        def worker():
            return clear_tag(paths)

        def finished(payload) -> None:
            cleared, errors = payload
            self.tag_status.update({path: False for path in paths})
            self.result_paths = paths
            self.render_results()
            suffix = f" · {len(errors)} 条提示" if errors else ""
            self.status.set(f"清除完成 · {cleared} 张图片已移除 AI 标签{suffix}")

        self.run_background(f"正在清除 {len(paths)} 张图片的 AI 标签", worker, finished)

    def refresh_tag_status(self) -> None:
        if not self.loaded_paths:
            return
        paths = self.loaded_paths.copy()

        def worker():
            return read_tagged(paths)

        def finished(payload) -> None:
            tagged, errors = payload
            tagged_set = set(tagged)
            self.tag_status = {path: path in tagged_set for path in paths}
            self.result_paths = paths
            self.render_results()
            suffix = f" · {len(errors)} 条提示" if errors else ""
            self.status.set(f"已载入 {len(paths)} 张图片 · {len(tagged)} 张已带 AI 标签{suffix}")

        self.run_background(f"正在读取 {len(paths)} 张图片的标签信息", worker, finished)

    def scan_loaded(self) -> None:
        if not self.loaded_paths:
            self.status.set("请先拖入需要读取标签的图片")
            return
        paths = self.loaded_paths.copy()

        def worker():
            return read_tagged(paths)

        def finished(payload) -> None:
            tagged, errors = payload
            self.result_paths = tagged
            self.render_results()
            suffix = f" · {len(errors)} 条提示" if errors else ""
            self.status.set(f"核验完成 · {len(paths)} 张图片中有 {len(tagged)} 张带 AI 标签{suffix}")

        self.run_background(f"正在核验 {len(paths)} 张图片的 AI 标签", worker, finished)

    def write_selected(self) -> None:
        folder = self.current_folder()
        if not folder:
            return
        selected = filedialog.askopenfilenames(
            title="选择要写入标签的图片",
            initialdir=folder,
            filetypes=[("支持的图片", "*.jpg *.jpeg *.png *.webp *.tif *.tiff")],
        )
        files = [Path(p).resolve() for p in selected]
        self._write(files)

    def write_all(self) -> None:
        folder = self.current_folder()
        if not folder:
            return
        files = image_files(folder)
        if not files:
            self.status.set("当前文件夹内没有支持的图片")
            return
        self._write(files)

    def _write(self, files: list[Path], on_completed=None) -> None:
        if not files:
            return
        try:
            suffix = validate_suffix(self.suffix.get())
        except Exception as exc:
            self.status.set(f"尾缀不可用 · {exc}")
            return
        keep_source = self.mode_value.get() >= 0.5

        def worker():
            return process_images(files, keep_source, suffix)

        def finished(payload) -> None:
            outputs, errors = payload
            self.loaded_paths = outputs
            self.result_paths = outputs
            self.tag_status = {path: True for path in outputs}
            self.render_results()
            if errors:
                self.status.set(f"已完成 · 成功 {len(outputs)} 张，另有 {len(errors)} 条警告")
            else:
                self.status.set(f"写入并核验完成 · {len(outputs)} 张图片已带标签")
            if outputs and on_completed is not None:
                on_completed()
            if outputs and self.open_output_dir.get():
                try:
                    os.startfile(str(outputs[0].parent))
                except OSError as exc:
                    self.status.set(f"写入完成 · 无法自动打开输出目录：{exc}")

        self.run_background(
            f"正在写入并核验 {len(files)} 张图片 · 请勿关闭工具",
            worker,
            finished,
        )

    def scan(self) -> None:
        folder = self.current_folder()
        if not folder:
            return

        files = image_files(folder)
        if not files:
            self.result_paths = []
            self.render_results()
            self.status.set("扫描完成 · 当前文件夹没有支持的图片")
            return

        def worker():
            tagged, errors = read_tagged(files)
            return tagged, errors

        def finished(payload) -> None:
            tagged, errors = payload
            self.result_paths = tagged
            self.render_results()
            suffix = f" · {len(errors)} 条提示" if errors else ""
            self.status.set(f"扫描完成 · {len(files)} 张图片中有 {len(tagged)} 张已带标签{suffix}")

        self.run_background(
            f"正在扫描 {len(files)} 张图片的 XMP 标签",
            worker,
            finished,
        )

    def make_thumbnail(self, path: Path, size: int) -> ImageTk.PhotoImage | None:
        try:
            with Image.open(path) as image:
                image.thumbnail((size, size), Image.Resampling.LANCZOS)
                preview = image.convert("RGB")
            return ImageTk.PhotoImage(preview)
        except Exception:
            return None

    def render_results(self) -> None:
        self.thumb_after_id = None
        for child in self.result_host.winfo_children():
            child.destroy()
        self.photo_refs = []
        self.result_tree = None
        if self.result_paths:
            tagged_count = sum(self.tag_status.get(path) is True for path in self.result_paths)
            self.result_count.set(f"{len(self.result_paths)} 张 · {tagged_count} 张已带标签")
        else:
            self.result_count.set("等待拖入")
        self.refresh_action_states()
        if not self.result_paths:
            empty = ttk.Frame(self.result_host, style="Surface.TFrame")
            empty.pack(fill="both", expand=True)
            empty_content = ttk.Frame(empty, style="Surface.TFrame")
            empty_content.place(relx=0.5, rely=0.5, anchor="center")
            ttk.Label(empty_content, text="拖入图片开始", style="Section.TLabel").pack()
            ttk.Label(
                empty_content,
                text="支持拖入多张图片或一个文件夹，标签状态会自动显示在缩略图右侧。",
                style="SurfaceMuted.TLabel",
            ).pack(pady=(8, 0))
            self._apply_gradient_labels(empty)
            return
        size = int(self.thumb_size.get())
        if self.view_mode.get() == "grid":
            self.render_grid(size)
        else:
            self.render_list(size)
        self._apply_gradient_labels(self.result_host)

    def render_list(self, size: int) -> None:
        ttk.Style(self).configure("Treeview", rowheight=size + 16)
        tree = ttk.Treeview(
            self.result_host,
            columns=("tag", "path"),
            displaycolumns=("tag",),
            show="tree headings",
            selectmode="extended",
        )
        tree.heading("#0", text="缩略图")
        tree.heading("tag", text="标签信息")
        tree.column("#0", width=size + 24, stretch=False, anchor="center")
        tree.column("tag", width=520, stretch=True)
        tree.column("path", width=0, stretch=False)
        tree.configure(height=max(4, 430 // max(size, 40)))
        scroll = ttk.Scrollbar(
            self.result_host,
            orient="vertical",
            command=tree.yview,
            style="Glass.Vertical.TScrollbar",
        )
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.result_tree = tree
        for path in self.result_paths:
            state = self.tag_status.get(path)
            tag_text = (
                f"已写入 · {TAG}"
                if state is True
                else "未检测到 AI 标签"
                if state is False
                else "正在读取标签…"
            )
            photo = self.make_thumbnail(path, size)
            if photo:
                self.photo_refs.append(photo)
                tree.insert("", "end", image=photo, values=(tag_text, str(path)))
            else:
                tree.insert("", "end", text="无法预览", values=(tag_text, str(path)))
        children = tree.get_children()
        if children:
            tree.selection_set(children)

    def render_grid(self, size: int) -> None:
        canvas = tk.Canvas(self.result_host, highlightthickness=0, background=self.SURFACE)
        scroll = ttk.Scrollbar(
            self.result_host,
            orient="vertical",
            command=canvas.yview,
            style="Glass.Vertical.TScrollbar",
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        inner = ttk.Frame(canvas, style="Surface.TFrame")
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        width = max(self.result_host.winfo_width(), 620)
        columns = max(1, width // (size + 90))
        for index, path in enumerate(self.result_paths):
            card = ttk.Frame(inner, style="Card.TFrame", padding=8)
            card.grid(row=index // columns, column=index % columns, padx=5, pady=5, sticky="nsew")
            photo = self.make_thumbnail(path, size)
            if photo:
                self.photo_refs.append(photo)
                ttk.Label(card, image=photo, style="Surface.TLabel").pack()
            else:
                ttk.Label(
                    card,
                    text="无法预览",
                    width=16,
                    anchor="center",
                    style="SurfaceMuted.TLabel",
                ).pack(ipady=size // 3)
            ttk.Label(
                card,
                text=path.name,
                wraplength=size + 50,
                anchor="center",
                style="Surface.TLabel",
            ).pack(fill="x", pady=(6, 2))
            state = self.tag_status.get(path)
            ttk.Label(
                card,
                text=TAG if state is True else "未检测到 AI 标签" if state is False else "正在读取标签…",
                wraplength=size + 50,
                style="SurfaceMuted.TLabel",
            ).pack(fill="x", pady=(0, 2))
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(window, width=max(width - 20, 200))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"))

    def copy_paths(self) -> None:
        if not self.result_paths:
            self.status.set("当前清单为空 · 请先拖入图片")
            return
        paths = self.result_paths
        if self.result_tree:
            selected = self.result_tree.selection()
            if selected:
                paths = [Path(self.result_tree.item(item, "values")[-1]) for item in selected]
        self.clipboard_clear()
        self.clipboard_append("\r\n".join(map(str, paths)))
        self.status.set(f"已复制 {len(paths)} 条完整路径")


if __name__ == "__main__":
    App().mainloop()
