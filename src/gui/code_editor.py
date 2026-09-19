"""
Mermaid Code Editor with synchronized line numbers and error highlighting.
"""

import tkinter as tk
from tkinter import ttk


class LineNumbers(tk.Canvas):
    """
    Canvas widget for rendering synchronized line numbers next to a Text widget.
    """
    def __init__(self, parent, text_widget, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.text_widget = text_widget
        self.config(width=42, bg="#f1f5f9", highlightthickness=0)
        self.highlighted_line = None

    def redraw(self, *args):
        self.delete("all")
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            
            # Check if this is the highlighted error line
            if self.highlighted_line and linenum == str(self.highlighted_line):
                # Red dot marker
                self.create_oval(4, y + 2, 12, y + 10, fill="#ef4444", outline="")
                text_color = "#ef4444"
            else:
                text_color = "#64748b"

            self.create_text(36, y, anchor="ne", text=linenum, font=("Consolas", 10), fill=text_color)
            i = self.text_widget.index(f"{i}+1line")

    def highlight_line(self, line_num: int):
        self.highlighted_line = line_num
        self.redraw()

    def clear_highlight(self):
        self.highlighted_line = None
        self.redraw()


class MermaidCodeEditor(ttk.Frame):
    """
    Code editor frame containing a line-numbered text area with undo support.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.text = tk.Text(
            self,
            wrap=tk.NONE,
            undo=True,
            font=("Consolas", 11),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#2563eb",
            selectbackground="#bfdbfe",
            selectforeground="#1e3a8a",
            relief=tk.FLAT,
            padx=8,
            pady=6,
            highlightthickness=1,
            highlightcolor="#3b82f6",
            highlightbackground="#cbd5e1"
        )

        self.vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._on_vscroll)
        self.hsb = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.text.xview)

        self.text.configure(yscrollcommand=self._on_text_scroll, xscrollcommand=self.hsb.set)

        self.linenumbers = LineNumbers(self, self.text)

        # Layout
        self.linenumbers.grid(row=0, column=0, sticky="ns")
        self.text.grid(row=0, column=1, sticky="nsew")
        self.vsb.grid(row=0, column=2, sticky="ns")
        self.hsb.grid(row=1, column=1, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Event bindings
        self.text.bind("<KeyRelease>", self._on_change)
        self.text.bind("<MouseWheel>", self._on_change)
        self.text.bind("<Button-1>", self._on_change)
        self.text.bind("<Configure>", self._on_change)

        # Configure tag for error highlighting
        self.text.tag_configure("error_line", background="#fee2e2", underline=True)

    def _on_vscroll(self, *args):
        self.text.yview(*args)
        self.linenumbers.redraw()

    def _on_text_scroll(self, *args):
        self.vsb.set(*args)
        self.linenumbers.redraw()

    def _on_change(self, event=None):
        self.linenumbers.redraw()

    def get_text(self) -> str:
        return self.text.get("1.0", tk.END).strip()

    def set_text(self, content: str):
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.clear_error()
        self.linenumbers.redraw()

    def clear(self):
        self.text.delete("1.0", tk.END)
        self.clear_error()
        self.linenumbers.redraw()

    def highlight_error(self, line_num: int):
        self.clear_error()
        if line_num > 0:
            self.text.tag_add("error_line", f"{line_num}.0", f"{line_num}.end")
            self.text.see(f"{line_num}.0")
            self.linenumbers.highlight_line(line_num)

    def clear_error(self):
        self.text.tag_remove("error_line", "1.0", tk.END)
        self.linenumbers.clear_highlight()
