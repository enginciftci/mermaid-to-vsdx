"""
Interactive Image Preview Panel for Visio visual verification screenshots.
Supports Zoom, Pan, Fit to View, and metadata inspection.
"""

import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


class ImagePreviewPanel(ttk.Frame):
    """
    Interactive zoomable and pannable image viewer canvas for visual verification.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.pil_image: Image.Image = None
        self.tk_image = None
        self.scale = 1.0
        self.image_path = ""
        self.meta_info = {}
        self.i18n = None

        # Top Control Bar
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(fill=tk.X, padx=4, pady=4)

        self.btn_fit = ttk.Button(self.toolbar, text="🔍 Ekrana Sığdır (Fit)", command=self.fit_to_view)
        self.btn_fit.pack(side=tk.LEFT, padx=2)

        self.btn_zoom_in = ttk.Button(self.toolbar, text="➕ Yakınlaştır (+)", command=self.zoom_in)
        self.btn_zoom_in.pack(side=tk.LEFT, padx=2)

        self.btn_zoom_out = ttk.Button(self.toolbar, text="➖ Uzaklaştır (-)", command=self.zoom_out)
        self.btn_zoom_out.pack(side=tk.LEFT, padx=2)

        self.btn_orig = ttk.Button(self.toolbar, text="1:1 Orijinal", command=self.reset_zoom)
        self.btn_orig.pack(side=tk.LEFT, padx=2)

        self.lbl_zoom = ttk.Label(self.toolbar, text="Ölçek: 100%", foreground="#64748b")
        self.lbl_zoom.pack(side=tk.RIGHT, padx=6)

        # Canvas with Scrollbars
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#f8fafc", highlightthickness=0)
        self.vsb = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.hsb = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(xscrollcommand=self.hsb.set, yscrollcommand=self.vsb.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")

        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        # Mouse Panning & Zooming
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._do_pan)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Configure>", self._on_resize)

        # Bottom Info Bar
        self.status_bar = ttk.Frame(self)
        self.status_bar.pack(fill=tk.X, padx=6, pady=4)

        self.lbl_info = ttk.Label(
            self.status_bar,
            text="Görsel Doğrulama: Henüz şema oluşturulmadı.",
            font=("Segoe UI", 9),
            foreground="#64748b"
        )
        self.lbl_info.pack(side=tk.LEFT)

    def set_language(self, i18n):
        """
        Updates UI strings based on the provided i18n localization instance.
        """
        self.i18n = i18n
        self._apply_language()

    def _apply_language(self):
        if not self.i18n:
            return

        self.btn_fit.config(text=self.i18n("btn_fit"))
        self.btn_zoom_in.config(text=self.i18n("btn_zoom_in"))
        self.btn_zoom_out.config(text=self.i18n("btn_zoom_out"))
        self.btn_orig.config(text=self.i18n("btn_orig"))
        self.lbl_zoom.config(text=self.i18n("scale_label", scale=int(self.scale * 100)))

        if not self.pil_image:
            self.lbl_info.config(text=self.i18n("preview_status_empty"))
            self._show_placeholder()
        else:
            w = self.pil_image.width
            h = self.pil_image.height
            size_kb = self.meta_info.get("file_size_kb", 0)
            time_sec = self.meta_info.get("render_time_sec", 0.0)
            info_text = f"✓ {self.i18n('preview_status_loaded', width=w, height=h, size_kb=size_kb, time_sec=time_sec)}"
            self.lbl_info.config(text=info_text)

    def _show_placeholder(self):
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 400)
        h = max(self.canvas.winfo_height(), 300)
        msg = (
            self.i18n("preview_placeholder")
            if self.i18n
            else "🎨 Visio Görsel Doğrulama Önizlemesi\n\n'Visio'ya Dönüştür' butonuna basarak\nşemanızı oluşturabilir ve canlı önizleyebilirsiniz."
        )
        self.canvas.create_text(
            w / 2, h / 2,
            text=msg,
            font=("Segoe UI", 11),
            fill="#94a3b8",
            justify=tk.CENTER,
            tags="placeholder"
        )

    def load_image(self, image_path: str, meta_info: dict = None):
        """
        Loads a new screenshot into the viewer and triggers fit to view.
        """
        if not os.path.exists(image_path):
            return

        self.image_path = image_path
        self.meta_info = meta_info or {}
        self.pil_image = Image.open(image_path)
        
        w = self.pil_image.width
        h = self.pil_image.height
        size_kb = self.meta_info.get("file_size_kb", 0)
        time_sec = self.meta_info.get("render_time_sec", 0.0)

        if self.i18n:
            info_text = f"✓ {self.i18n('preview_status_loaded', width=w, height=h, size_kb=size_kb, time_sec=time_sec)}"
        else:
            info_text = f"✓ Doğrulandı: {w} × {h} px | {size_kb} KB | {os.path.basename(image_path)}"
        self.lbl_info.config(text=info_text, foreground="#166534")

        self.fit_to_view()

    def fit_to_view(self):
        if not self.pil_image:
            return

        c_width = max(self.canvas.winfo_width(), 300)
        c_height = max(self.canvas.winfo_height(), 200)

        img_w, img_h = self.pil_image.size
        scale_w = (c_width - 30) / float(img_w)
        scale_h = (c_height - 30) / float(img_h)
        self.scale = max(min(scale_w, scale_h), 0.05)

        self._render_scaled_image()

    def zoom_in(self):
        if not self.pil_image:
            return
        self.scale = min(self.scale * 1.25, 4.0)
        self._render_scaled_image()

    def zoom_out(self):
        if not self.pil_image:
            return
        self.scale = max(self.scale / 1.25, 0.08)
        self._render_scaled_image()

    def reset_zoom(self):
        if not self.pil_image:
            return
        self.scale = 1.0
        self._render_scaled_image()

    def _render_scaled_image(self):
        if not self.pil_image:
            return

        target_w = max(int(self.pil_image.width * self.scale), 10)
        target_h = max(int(self.pil_image.height * self.scale), 10)

        # High-quality bicubic resampling
        resized = self.pil_image.resize((target_w, target_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.create_image(15, 15, anchor="nw", image=self.tk_image)
        self.canvas.config(scrollregion=(0, 0, target_w + 30, target_h + 30))

        if self.i18n:
            self.lbl_zoom.config(text=self.i18n("scale_label", scale=int(self.scale * 100)))
        else:
            self.lbl_zoom.config(text=f"Ölçek: {int(self.scale * 100)}%")

    def _start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_mousewheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def _on_resize(self, event):
        if not self.pil_image:
            self._show_placeholder()
