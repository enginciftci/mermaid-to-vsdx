"""
Main Desktop Application Window for Mermaid to Visio (.vsdx) Converter.
Features Windows 11 Fluent styling (Light Theme Only), dual-pane editor and preview,
Turkish and English (US) multi-language support, Turkish character verification,
and 100% independent native OPC generation.
"""

import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from typing import Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

from .code_editor import MermaidCodeEditor
from .image_preview import ImagePreviewPanel
from .samples import SAMPLES
from .i18n import I18n, LANGUAGES
from ..parser import MermaidParseError, extract_mermaid_from_markdown
from ..visio import (
    convert_mermaid_to_visio,
    is_visio_installed,
    get_visio_version,
    open_in_visio,
    PALETTES,
    DEFAULT_PALETTE_NAME
)
from ..verifier import verify_and_capture_visio, render_vsdx_to_png
from ..utils.unicode_helper import (
    verify_turkish_chars,
    RECOMMENDED_FONTS,
    DEFAULT_FONT
)


class MermaidVisioApp(tk.Tk):
    """
    Main Application Window.
    Enforces Light Theme only and supports full dynamic i18n (Turkish & English US).
    """
    def __init__(self):
        super().__init__()

        # Localization manager
        self.i18n = I18n("tr")

        self.title(self.i18n("app_title"))
        self.geometry("1380x860")
        self.minsize(1050, 680)

        # State
        self.current_vsdx_path = ""
        self.current_screenshot_path = ""
        self.is_converting = False
        self.visio_available = is_visio_installed()

        # Enforce Clean Fluent Light Theme (No dark theme toggle)
        if HAS_SV_TTK:
            try:
                sv_ttk.set_theme("light")
            except Exception:
                pass

        self._build_ui()
        self._check_visio_status(log=True)

        # Load default sample
        first_sample_name = list(SAMPLES.keys())[0]
        self.combo_samples.set(first_sample_name)
        self._on_sample_selected()

    def _build_ui(self):
        # 1. Header Toolbar
        self.header_frame = ttk.Frame(self, padding=(12, 8))
        self.header_frame.pack(fill=tk.X)

        self.lbl_title = ttk.Label(
            self.header_frame,
            text=self.i18n("header_title"),
            font=("Segoe UI", 13, "bold")
        )
        self.lbl_title.pack(side=tk.LEFT)

        # Visio Status Badge
        self.lbl_visio_status = ttk.Label(
            self.header_frame,
            text=self.i18n("visio_checking"),
            font=("Segoe UI", 9, "bold"),
            padding=(8, 4)
        )
        self.lbl_visio_status.pack(side=tk.LEFT, padx=16)

        # Multi-Language Selector (Turkish and English USA)
        lang_frame = ttk.Frame(self.header_frame)
        lang_frame.pack(side=tk.RIGHT, padx=4)

        self.lbl_lang = ttk.Label(
            lang_frame,
            text=self.i18n("language_label"),
            font=("Segoe UI", 9)
        )
        self.lbl_lang.pack(side=tk.LEFT, padx=(0, 6))

        self.combo_lang = ttk.Combobox(
            lang_frame,
            values=list(LANGUAGES.values()),
            state="readonly",
            width=17
        )
        self.combo_lang.set(LANGUAGES["tr"])
        self.combo_lang.pack(side=tk.LEFT)
        self.combo_lang.bind("<<ComboboxSelected>>", self._on_language_changed)

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # 2. Main Split Panes (Left: Editor, Right: Preview)
        self.main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Left Container (Editor & Configuration)
        self.left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.left_frame, weight=1)

        # Right Container (Verification & Visual Preview)
        self.right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.right_frame, weight=1)

        self._build_left_panel()
        self._build_right_panel()

        # 3. Bottom Status and Log Console
        self._build_bottom_panel()

    def _build_left_panel(self):
        # Preset Selector Bar
        preset_bar = ttk.Frame(self.left_frame, padding=(4, 4))
        preset_bar.pack(fill=tk.X)

        self.lbl_samples = ttk.Label(preset_bar, text=self.i18n("sample_templates"))
        self.lbl_samples.pack(side=tk.LEFT, padx=(0, 6))

        self.combo_samples = ttk.Combobox(
            preset_bar,
            values=list(SAMPLES.keys()),
            state="readonly",
            width=50
        )
        self.combo_samples.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.combo_samples.bind("<<ComboboxSelected>>", self._on_sample_selected)

        self.btn_load = ttk.Button(preset_bar, text=self.i18n("load_file"), command=self._load_file)
        self.btn_load.pack(side=tk.LEFT, padx=3)

        self.btn_save = ttk.Button(preset_bar, text=self.i18n("save_file"), command=self._save_file)
        self.btn_save.pack(side=tk.LEFT, padx=3)

        self.btn_clear = ttk.Button(preset_bar, text=self.i18n("clear_editor"), command=self._clear_editor)
        self.btn_clear.pack(side=tk.LEFT, padx=3)

        # Mermaid Code Editor
        self.editor = MermaidCodeEditor(self.left_frame)
        self.editor.pack(fill=tk.BOTH, expand=True, pady=4)

        # Conversion Configuration Bar
        self.config_bar = ttk.LabelFrame(self.left_frame, text=self.i18n("style_settings"), padding=8)
        self.config_bar.pack(fill=tk.X, pady=(4, 2))

        # Palette selection
        self.lbl_palette = ttk.Label(self.config_bar, text=self.i18n("palette_label"))
        self.lbl_palette.grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self.combo_palette = ttk.Combobox(
            self.config_bar,
            values=list(PALETTES.keys()),
            state="readonly",
            width=32
        )
        self.combo_palette.set(DEFAULT_PALETTE_NAME)
        self.combo_palette.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        # Font selection
        self.lbl_font = ttk.Label(self.config_bar, text=self.i18n("font_label"))
        self.lbl_font.grid(row=0, column=2, sticky="w", padx=(12, 4), pady=2)
        self.combo_font = ttk.Combobox(
            self.config_bar,
            values=RECOMMENDED_FONTS,
            state="readonly",
            width=18
        )
        self.combo_font.set(DEFAULT_FONT)
        self.combo_font.grid(row=0, column=3, sticky="w", padx=4, pady=2)

        # Action Buttons
        btn_frame = ttk.Frame(self.left_frame, padding=(4, 6))
        btn_frame.pack(fill=tk.X)

        self.btn_convert = ttk.Button(
            btn_frame,
            text=self.i18n("btn_convert"),
            command=self._start_conversion,
            style="Accent.TButton" if HAS_SV_TTK else "TButton"
        )
        self.btn_convert.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.btn_export = ttk.Button(
            btn_frame,
            text=self.i18n("btn_export_vsdx"),
            command=self._export_vsdx_direct
        )
        self.btn_export.pack(side=tk.LEFT, padx=3)

        self.btn_export_png = ttk.Button(
            btn_frame,
            text=self.i18n("btn_export_png"),
            command=self._export_png_direct,
            state=tk.DISABLED
        )
        self.btn_export_png.pack(side=tk.LEFT, padx=3)

        open_btn_text = self.i18n("btn_open_visio") if self.visio_available else self.i18n("btn_open_general")
        self.btn_open_visio = ttk.Button(
            btn_frame,
            text=open_btn_text,
            command=self._open_in_visio,
            state=tk.DISABLED
        )
        self.btn_open_visio.pack(side=tk.LEFT, padx=3)

    def _build_right_panel(self):
        # Verification Preview Panel
        self.preview_panel = ImagePreviewPanel(self.right_frame)
        self.preview_panel.pack(fill=tk.BOTH, expand=True)
        self.preview_panel.set_language(self.i18n)

    def _build_bottom_panel(self):
        bottom_frame = ttk.Frame(self, padding=(8, 4))
        bottom_frame.pack(fill=tk.X)

        # Progress bar
        self.progress_bar = ttk.Progressbar(bottom_frame, mode="indeterminate")
        self.progress_bar.pack(fill=tk.X, pady=(0, 4))

        # Status & Activity Console (Light theme styling)
        self.console_frame = ttk.LabelFrame(bottom_frame, text=self.i18n("console_title"), padding=4)
        self.console_frame.pack(fill=tk.X)

        self.txt_log = tk.Text(
            self.console_frame,
            height=5,
            font=("Consolas", 9),
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#0f172a",
            selectbackground="#e2e8f0",
            selectforeground="#0f172a",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        log_scroll = ttk.Scrollbar(self.console_frame, orient=tk.VERTICAL, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=log_scroll.set)

        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._log(self.i18n("log_ready"))

    def _check_visio_status(self, log: bool = True):
        if self.visio_available:
            ver = get_visio_version()
            self.lbl_visio_status.config(
                text=self.i18n("visio_ready", ver=ver),
                foreground="#15803d"
            )
            if log:
                self._log(self.i18n("log_visio_detected", ver=ver))
        else:
            self.lbl_visio_status.config(
                text=self.i18n("visio_independent"),
                foreground="#0284c7"
            )
            if log:
                self._log(self.i18n("log_visio_independent_info"))

    def _on_language_changed(self, event=None):
        selected_display = self.combo_lang.get()
        for code, display in LANGUAGES.items():
            if display == selected_display:
                self.i18n.set_language(code)
                break
        self._apply_language()
        self._log(self.i18n("log_lang_changed"))

    def _apply_language(self):
        """
        Dynamically updates all UI texts and labels when interface language switches.
        """
        self.title(self.i18n("app_title"))
        self.lbl_title.config(text=self.i18n("header_title"))
        self.lbl_lang.config(text=self.i18n("language_label"))
        self._check_visio_status(log=False)

        self.lbl_samples.config(text=self.i18n("sample_templates"))
        self.btn_load.config(text=self.i18n("load_file"))
        self.btn_save.config(text=self.i18n("save_file"))
        self.btn_clear.config(text=self.i18n("clear_editor"))

        self.config_bar.config(text=self.i18n("style_settings"))
        self.lbl_palette.config(text=self.i18n("palette_label"))
        self.lbl_font.config(text=self.i18n("font_label"))

        self.btn_convert.config(text=self.i18n("btn_convert"))
        self.btn_export.config(text=self.i18n("btn_export_vsdx"))
        self.btn_export_png.config(text=self.i18n("btn_export_png"))

        open_btn_text = self.i18n("btn_open_visio") if self.visio_available else self.i18n("btn_open_general")
        self.btn_open_visio.config(text=open_btn_text)

        self.console_frame.config(text=self.i18n("console_title"))
        self.preview_panel.set_language(self.i18n)

    def _on_sample_selected(self, event=None):
        name = self.combo_samples.get()
        if name in SAMPLES:
            self.editor.set_text(SAMPLES[name])
            self._log(self.i18n("log_sample_loaded", name=name))

    def _load_file(self):
        is_tr = self.i18n.current_lang == "tr"
        path = filedialog.askopenfilename(
            filetypes=[
                ("Tüm Desteklenen Çizimler" if is_tr else "All Supported Diagrams", "*.mmd *.mermaid *.md *.markdown *.txt"),
                ("Markdown Belgeleri (*.md)" if is_tr else "Markdown Documents (*.md)", "*.md *.markdown"),
                ("Mermaid Dosyaları (*.mmd)" if is_tr else "Mermaid Files (*.mmd)", "*.mmd *.mermaid"),
                ("Metin Dosyaları (*.txt)" if is_tr else "Text Files (*.txt)", "*.txt"),
                ("Tüm Dosyalar" if is_tr else "All Files", "*.*")
            ]
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                content = extract_mermaid_from_markdown(raw_content)
                if content != raw_content.strip():
                    self._log(self.i18n("log_markdown_extracted", path=path))
                else:
                    self._log(self.i18n("log_file_loaded", path=path))

                self.editor.set_text(content)
            except Exception as err:
                messagebox.showerror(self.i18n("error_title"), f"{err}")

    def _save_file(self):
        is_tr = self.i18n.current_lang == "tr"
        path = filedialog.asksaveasfilename(
            defaultextension=".mmd",
            filetypes=[
                ("Mermaid Dosyası (*.mmd)" if is_tr else "Mermaid File (*.mmd)", "*.mmd"),
                ("Tüm Dosyalar (*.*)" if is_tr else "All Files (*.*)", "*.*")
            ]
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.editor.get_text())
                self._log(self.i18n("log_file_saved", path=path))
            except Exception as err:
                messagebox.showerror(self.i18n("error_title"), f"{err}")

    def _clear_editor(self):
        if messagebox.askyesno(self.i18n("clear_confirm_title"), self.i18n("clear_confirm_msg")):
            self.editor.clear()
            self._log(self.i18n("editor_cleared"))

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.txt_log.see(tk.END)

    def _start_conversion(self):
        if self.is_converting:
            return

        code = self.editor.get_text()
        if not code:
            messagebox.showwarning(self.i18n("warn_title"), self.i18n("warn_no_code"))
            return

        if not self.visio_available:
            self._log(self.i18n("log_visio_independent_info"))

        # Turkish Character Analysis
        tr_info = verify_turkish_chars(code)
        if tr_info["has_turkish"]:
            self._log(
                self.i18n(
                    "log_turkish_detected",
                    total=tr_info["total_turkish_chars"],
                    chars=", ".join(tr_info["char_counts"].keys())
                )
            )

        # Disable UI during conversion
        self.is_converting = True
        self.btn_convert.config(state=tk.DISABLED)
        self.progress_bar.start(10)
        self.editor.clear_error()

        # Run conversion in background worker thread to prevent UI freezing
        thread = threading.Thread(target=self._run_conversion_worker, args=(code,), daemon=True)
        thread.start()

    def _export_vsdx_direct(self):
        """
        Exports the Mermaid diagram directly to a .vsdx file chosen by the user
        without opening Microsoft Visio.
        """
        code = self.editor.get_text()
        if not code:
            messagebox.showwarning(self.i18n("warn_title"), self.i18n("warn_no_code"))
            return

        is_tr = self.i18n.current_lang == "tr"
        default_name = "diagram.vsdx"
        save_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".vsdx",
            filetypes=[
                ("Visio Çizimi (*.vsdx)" if is_tr else "Visio Diagram (*.vsdx)", "*.vsdx"),
                ("Tüm Dosyalar (*.*)" if is_tr else "All Files (*.*)", "*.*")
            ]
        )
        if not save_path:
            return

        palette_name = self.combo_palette.get()
        font_name = self.combo_font.get()

        try:
            self._log(self.i18n("log_export_vsdx", name=os.path.basename(save_path)))
            # Use native headless engine directly to guarantee Visio is NOT launched
            convert_mermaid_to_visio(
                mermaid_code=code,
                output_vsdx_path=save_path,
                palette_name=palette_name,
                font_name=font_name,
                engine="native"
            )
            self.current_vsdx_path = save_path
            if self.visio_available:
                self.btn_open_visio.config(state=tk.NORMAL)
            self._log(self.i18n("log_export_vsdx_success", path=save_path))
            messagebox.showinfo(self.i18n("success_title"), self.i18n("vsdx_exported_msg", path=save_path))
        except Exception as err:
            self._log(f"Export Error: {err}")
            messagebox.showerror(self.i18n("error_title"), f"{err}")

    def _run_conversion_worker(self, code: str):
        palette_name = self.combo_palette.get()
        font_name = self.combo_font.get()

        out_dir = os.path.abspath("output")
        ver_dir = os.path.abspath("verification_output")
        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(ver_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        vsdx_filename = f"diagram_{timestamp}.vsdx"
        vsdx_path = os.path.join(out_dir, vsdx_filename)

        try:
            self._log(self.i18n("log_step_1"))
            time.sleep(0.05)

            diag_type, generated_path = convert_mermaid_to_visio(
                mermaid_code=code,
                output_vsdx_path=vsdx_path,
                palette_name=palette_name,
                font_name=font_name
            )

            self._log(self.i18n("log_step_2", name=os.path.basename(generated_path)))

            # Visual verification / preview capture:
            # 1. Native Pillow renderer provides instant preview without Visio (100% headless)
            # 2. If Visio is installed, COM capture can also be utilized
            verification_result = None
            self._log(self.i18n("log_step_3"))
            try:
                preview_png = os.path.join(ver_dir, f"{os.path.splitext(vsdx_filename)[0]}_preview.png")
                verification_result = render_vsdx_to_png(
                    vsdx_path=generated_path,
                    output_image_path=preview_png
                )
            except Exception as r_err:
                self._log(f"ℹ Preview notice: {r_err}")

            if not verification_result and self.visio_available:
                try:
                    verification_result = verify_and_capture_visio(
                        vsdx_path=generated_path,
                        verification_dir=ver_dir
                    )
                except Exception as v_err:
                    self._log(f"ℹ Visio COM capture skipped: {v_err}")

            # Post completion to main thread
            self.after(0, self._on_conversion_success, generated_path, verification_result)

        except MermaidParseError as parse_err:
            self.after(0, self._on_conversion_parse_error, parse_err)
        except Exception as exc:
            self.after(0, self._on_conversion_error, str(exc))

    def _on_conversion_success(self, vsdx_path: str, ver_result: Optional[dict]):
        self.is_converting = False
        self.btn_convert.config(state=tk.NORMAL)
        self.progress_bar.stop()

        self.current_vsdx_path = vsdx_path
        self.btn_open_visio.config(state=tk.NORMAL)

        if ver_result:
            self.current_screenshot_path = ver_result["image_path"]
            self.preview_panel.load_image(self.current_screenshot_path, ver_result)
            if hasattr(self, 'btn_export_png'):
                self.btn_export_png.config(state=tk.NORMAL)
            
            is_tr = self.i18n.current_lang == "tr"
            if ver_result.get("engine") != "native_pillow":
                engine_str = "Visio COM"
            else:
                engine_str = "Dahili Vektör Motoru" if is_tr else "Native Vector Engine"

            self._log(
                self.i18n(
                    "log_success",
                    engine=engine_str,
                    width=ver_result["width"],
                    height=ver_result["height"],
                    size_kb=ver_result["file_size_kb"],
                    time_sec=ver_result["render_time_sec"]
                )
            )
        else:
            self._log(f"✓ Visio: {os.path.basename(vsdx_path)}")

    def _export_png_direct(self):
        """
        Exports the current preview diagram as a high-resolution PNG image.
        """
        if not self.current_screenshot_path or not os.path.exists(self.current_screenshot_path):
            messagebox.showwarning(self.i18n("warn_title"), self.i18n("warn_no_preview"))
            return

        is_tr = self.i18n.current_lang == "tr"
        save_path = filedialog.asksaveasfilename(
            initialfile="diagram_preview.png",
            defaultextension=".png",
            filetypes=[
                ("PNG Resmi (*.png)" if is_tr else "PNG Image (*.png)", "*.png"),
                ("Tüm Dosyalar (*.*)" if is_tr else "All Files (*.*)", "*.*")
            ]
        )
        if not save_path:
            return

        try:
            import shutil
            shutil.copyfile(self.current_screenshot_path, save_path)
            self._log(self.i18n("log_export_png_success", path=save_path))
            messagebox.showinfo(self.i18n("success_title"), self.i18n("png_exported_msg", path=save_path))
        except Exception as err:
            messagebox.showerror(self.i18n("error_title"), f"{err}")

    def _on_conversion_parse_error(self, err: MermaidParseError):
        self.is_converting = False
        self.btn_convert.config(state=tk.NORMAL)
        self.progress_bar.stop()

        if err.line_number > 0:
            self.editor.highlight_error(err.line_number)
            self._log(f"HATA / ERROR (Line {err.line_number}): {err.message}")
        else:
            self._log(f"HATA / ERROR: {err.message}")

        messagebox.showerror(
            self.i18n("error_title"),
            f"{err}\n\nCheck Mermaid syntax."
        )

    def _on_conversion_error(self, err_msg: str):
        self.is_converting = False
        self.btn_convert.config(state=tk.NORMAL)
        self.progress_bar.stop()

        self._log(f"SYSTEM ERROR: {err_msg}")
        messagebox.showerror(self.i18n("error_title"), f"{err_msg}")

    def _open_in_visio(self):
        if not self.current_vsdx_path:
            return

        if self.visio_available:
            try:
                self._log(f"Microsoft Visio: {self.current_vsdx_path}")
                open_in_visio(self.current_vsdx_path)
            except Exception as err:
                messagebox.showerror(self.i18n("error_title"), f"{err}")
        else:
            choice = messagebox.askyesnocancel(
                self.i18n("non_visio_dialog_title"),
                self.i18n("non_visio_dialog_msg"),
                default=messagebox.YES
            )
            if choice is True:
                try:
                    os.startfile(self.current_vsdx_path)
                except Exception as err:
                    messagebox.showerror(self.i18n("error_title"), f"{err}")
            elif choice is False:
                webbrowser.open("https://app.diagrams.net/")
                self._log(self.i18n("log_drawio_opened"))
            elif choice is None:
                folder = os.path.dirname(os.path.abspath(self.current_vsdx_path))
                os.startfile(folder)


def main():
    app = MermaidVisioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
