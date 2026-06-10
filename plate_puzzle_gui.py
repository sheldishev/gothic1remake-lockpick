#!/usr/bin/env python3
"""
Графическая оболочка для решателя головоломки с пластинками (Gothic 1 Remake lockpick).

Запуск:
  python plate_puzzle_gui.py
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Dict, List, Optional, Tuple

from i18n import APP_TITLE, Lang, t
from plate_puzzle_solver import (
    BUILTIN_EXAMPLE_INFLUENCES,
    BUILTIN_EXAMPLE_POSITIONS,
    DEFAULT_NUM_PLATES,
    MAX_PLATES,
    MAX_POS,
    MIN_PLATES,
    MIN_POS,
    TARGET,
    Move,
    PuzzleConfig,
    bfs_solve,
    format_solution_text,
)

INFLUENCE_STATES: List[Tuple[int, str, str, str]] = [
    (0, "·", "#e2e8f0", "#475569"),
    (1, "+", "#16a34a", "#ffffff"),
    (-1, "−", "#dc2626", "#ffffff"),
]
INFLUENCE_STYLE: Dict[int, Tuple[str, str, str]] = {
    value: (text, bg, fg) for value, text, bg, fg in INFLUENCE_STATES
}

EXAMPLE_POSITIONS = BUILTIN_EXAMPLE_POSITIONS
EXAMPLE_LINKS: Dict[Tuple[int, int], int] = {
    (src, tgt): sign
    for src, targets in BUILTIN_EXAMPLE_INFLUENCES.items()
    for tgt, sign in targets.items()
}

FRAME_BG = "#ffffff"
HEADER_BG = "#7dd3fc"
HEADER_FG = "#0c4a6e"
ROW_LABEL_BG = "#f1f5f9"
ROW_LABEL_FG = "#0f172a"
DIAGONAL_BG = "#94a3b8"
POSITION_BG = "#dbeafe"
POSITION_FG = "#1e3a8a"
POSITION_HOVER = "#93c5fd"

CELL_PX = 48
LABEL_COL_PX = 54

InfluenceHover = Tuple[tk.IntVar, tk.Label, tk.Frame]
SolveCache = Tuple[List[int], List[Move], Dict[int, Dict[int, int]]]


class PlatePuzzleApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=FRAME_BG)

        self.lang: Lang = "ru"
        self.lang_var = tk.StringVar(value=self.lang)
        self.num_plates = DEFAULT_NUM_PLATES
        self.plate_count_var = tk.IntVar(value=self.num_plates)
        self.position_vars: List[tk.IntVar] = []
        self.influence_cells: Dict[Tuple[int, int], Tuple[tk.IntVar, tk.Label]] = {}
        self._solve_thread: Optional[threading.Thread] = None
        self._position_scroll: Optional[tk.IntVar] = None
        self._influence_scroll: Optional[InfluenceHover] = None
        self._last_solution: Optional[SolveCache] = None
        self._status_key = "ready"

        self.lbl_plates: Optional[ttk.Label] = None
        self.example_btn: Optional[ttk.Button] = None
        self.clear_btn: Optional[ttk.Button] = None
        self.start_label: Optional[tk.Label] = None
        self.arrow_labels: List[tk.Label] = []

        self._build_ui()
        self.rebuild_plate_fields(self.num_plates)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=(10, 8, 10, 10))
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(main)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.lbl_plates = ttk.Label(toolbar, text=t("plates", self.lang))
        self.lbl_plates.pack(side=tk.LEFT, padx=(0, 6))
        count_frame = ttk.Frame(toolbar)
        count_frame.pack(side=tk.LEFT)
        for n in range(MIN_PLATES, MAX_PLATES + 1):
            ttk.Radiobutton(
                count_frame,
                text=str(n),
                value=n,
                variable=self.plate_count_var,
                command=self.on_plate_count_selected,
                width=3,
            ).pack(side=tk.LEFT, padx=1)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

        self.solve_btn = ttk.Button(toolbar, text=t("solve", self.lang), command=self.on_solve)
        self.solve_btn.pack(side=tk.LEFT)
        self.example_btn = ttk.Button(
            toolbar, text=t("example", self.lang), command=self.on_load_example
        )
        self.example_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.clear_btn = ttk.Button(
            toolbar, text=t("clear", self.lang), command=self.on_clear_result
        )
        self.clear_btn.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

        lang_frame = ttk.Frame(toolbar)
        lang_frame.pack(side=tk.LEFT)
        for code, label in (("ru", "RU"), ("en", "EN")):
            ttk.Radiobutton(
                lang_frame,
                text=label,
                value=code,
                variable=self.lang_var,
                command=self.on_language_changed,
                width=3,
            ).pack(side=tk.LEFT, padx=1)

        self.status_var = tk.StringVar(value=t("ready", self.lang))
        ttk.Label(toolbar, textvariable=self.status_var, foreground="#555").pack(side=tk.RIGHT)

        self.content_paned = ttk.Panedwindow(main, orient=tk.HORIZONTAL)
        self.content_paned.grid(row=1, column=0, sticky="nsew")

        self.grid_panel = ttk.Frame(self.content_paned, padding=(0, 0, 6, 0))
        result_panel = ttk.Frame(self.content_paned, padding=(6, 0, 0, 0))
        self.content_paned.add(self.grid_panel, weight=0)
        self.content_paned.add(result_panel, weight=1)

        self.grid_outer = tk.Frame(
            self.grid_panel,
            bg=FRAME_BG,
            bd=1,
            relief=tk.GROOVE,
            highlightthickness=0,
        )
        self.grid_outer.pack(anchor=tk.NW)

        self.grid_frame = tk.Frame(self.grid_outer, bg=FRAME_BG)
        self.grid_frame.grid(row=0, column=0, padx=12, pady=(12, 16))

        self.result_text = scrolledtext.ScrolledText(
            result_panel,
            wrap=tk.WORD,
            font=("Helvetica", 13),
            relief=tk.SUNKEN,
            borderwidth=1,
            padx=8,
            pady=6,
            width=34,
            spacing1=0,
            spacing3=6,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.tag_configure("step_label", font=("Helvetica", 10), foreground="#64748b")
        self.result_text.tag_configure(
            "step_body",
            font=("Helvetica", 13, "bold"),
            spacing1=4,
            spacing3=4,
        )
        self.result_text.configure(state=tk.DISABLED)

        self.root.bind_all("<MouseWheel>", self._on_global_wheel, add="+")
        for sequence in ("<Button-4>", "<Button-5>"):
            self.root.bind_all(sequence, self._on_global_wheel, add="+")

    def _set_status(self, key: str, **kwargs: object) -> None:
        self._status_key = key
        self.status_var.set(t(key, self.lang, **kwargs))

    def _apply_toolbar_texts(self) -> None:
        if self.lbl_plates:
            self.lbl_plates.configure(text=t("plates", self.lang))
        self.solve_btn.configure(text=t("solve", self.lang))
        if self.example_btn:
            self.example_btn.configure(text=t("example", self.lang))
        if self.clear_btn:
            self.clear_btn.configure(text=t("clear", self.lang))
        self.status_var.set(t(self._status_key, self.lang))

    def _apply_grid_labels(self) -> None:
        if self.start_label:
            self.start_label.configure(text=t("start", self.lang))
        for index, label in enumerate(self.arrow_labels, start=1):
            label.configure(text=t("influence_row", self.lang, n=index))

    def on_language_changed(self) -> None:
        self.lang = self.lang_var.get()  # type: ignore[assignment]
        self.root.title(APP_TITLE)
        self._apply_toolbar_texts()
        self._apply_grid_labels()
        self._refresh_solution_text()

    def _refresh_solution_text(self) -> None:
        if self._last_solution is None:
            return
        positions, moves, influences = self._last_solution
        config = PuzzleConfig(num_plates=len(positions))
        self.set_result_text(format_solution_text(positions, moves, influences, config, self.lang))

    def _configure_grid(self, num_plates: int) -> None:
        self.grid_frame.grid_columnconfigure(0, minsize=LABEL_COL_PX)
        for col in range(1, num_plates + 1):
            self.grid_frame.grid_columnconfigure(col, minsize=CELL_PX, uniform="plate_col")
        for row in range(num_plates + 2):
            self.grid_frame.grid_rowconfigure(row, minsize=CELL_PX, uniform="plate_row")

    def _grid_content_width(self, num_plates: int) -> int:
        cell_span = CELL_PX + 6
        return LABEL_COL_PX + num_plates * cell_span + 24

    def _layout_window(self) -> None:
        self.root.update_idletasks()
        frame_w = max(
            self.grid_frame.winfo_reqwidth(),
            self._grid_content_width(self.num_plates),
        )
        frame_h = self.grid_frame.winfo_reqheight()
        grid_w = frame_w + 28
        result_w = 320
        sash = grid_w + 12
        win_w = sash + result_w + 28
        win_h = max(420, frame_h + 120)
        self.root.minsize(sash + 160, min(400, win_h))
        self.content_paned.sashpos(0, sash)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.update_idletasks()
        self.content_paned.sashpos(0, sash)
        self.root.after(30, lambda s=sash: self.content_paned.sashpos(0, s))

    def _place(self, widget: tk.Widget, row: int, col: int) -> None:
        widget.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

    def _static_label(
        self,
        parent: tk.Misc,
        text: str,
        *,
        bg: str,
        fg: str,
        font: Tuple[str, int, str] = ("Helvetica", 11, "bold"),
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            anchor=tk.CENTER,
        )

    def _make_position_cell(self, parent: tk.Misc, var: tk.IntVar) -> tk.Frame:
        frame = tk.Frame(
            parent,
            bg=POSITION_BG,
            width=CELL_PX,
            height=CELL_PX,
            highlightthickness=1,
            highlightbackground="#93c5fd",
            cursor="hand2",
        )
        frame.grid_propagate(False)

        lbl = tk.Label(
            frame,
            textvariable=var,
            bg=POSITION_BG,
            fg=POSITION_FG,
            font=("Helvetica", 20, "bold"),
            anchor=tk.CENTER,
            cursor="hand2",
        )
        lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        def on_enter(_e: tk.Event) -> None:
            self._influence_scroll = None
            self._position_scroll = var
            frame.configure(bg=POSITION_HOVER, highlightbackground="#3b82f6")
            lbl.configure(bg=POSITION_HOVER)

        def on_leave(_e: tk.Event) -> None:
            self._position_scroll = None
            frame.configure(bg=POSITION_BG, highlightbackground="#93c5fd")
            lbl.configure(bg=POSITION_BG)

        for w in (frame, lbl):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", lambda e, v=var: self.bump_position(v, 1))
            w.bind("<Button-3>", lambda e, v=var: self.bump_position(v, -1))
            if sys.platform == "darwin":
                w.bind("<Button-2>", lambda e, v=var: self.bump_position(v, -1))

        return frame

    def _make_influence_cell(self, parent: tk.Misc, var: tk.IntVar) -> Tuple[tk.Frame, tk.Label]:
        text, bg, fg = INFLUENCE_STYLE[0]

        frame = tk.Frame(
            parent,
            bg=bg,
            width=CELL_PX,
            height=CELL_PX,
            highlightthickness=2,
            highlightbackground="#94a3b8",
            cursor="hand2",
        )
        frame.grid_propagate(False)

        lbl = tk.Label(
            frame,
            text=text,
            bg=bg,
            fg=fg,
            font=("Helvetica", 20, "bold"),
            anchor=tk.CENTER,
            cursor="hand2",
        )
        lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        def on_enter(_e: tk.Event) -> None:
            self._position_scroll = None
            self._influence_scroll = (var, lbl, frame)
            frame.configure(highlightbackground="#3b82f6")

        def on_leave(_e: tk.Event) -> None:
            self._influence_scroll = None
            frame.configure(highlightbackground="#94a3b8")

        def on_click(_e: tk.Event) -> None:
            self.set_influence_value(var, lbl, frame, 0)

        for w in (frame, lbl):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

        return frame, lbl

    def on_plate_count_selected(self) -> None:
        try:
            new_count = self.plate_count_var.get()
            PuzzleConfig(num_plates=new_count)
        except ValueError as exc:
            messagebox.showerror(t("error", self.lang), str(exc))
            self.plate_count_var.set(self.num_plates)
            return
        self.rebuild_plate_fields(new_count)

    def rebuild_plate_fields(self, num_plates: int) -> None:
        self.num_plates = num_plates
        self.plate_count_var.set(num_plates)

        for child in self.grid_frame.winfo_children():
            child.destroy()

        self.position_vars = []
        self.influence_cells = {}
        self.arrow_labels = []
        self.start_label = None
        self._position_scroll = None
        self._influence_scroll = None
        self._configure_grid(num_plates)

        self._place(
            self._static_label(self.grid_frame, "", bg=FRAME_BG, fg=ROW_LABEL_FG),
            0, 0,
        )

        for src in range(1, num_plates + 1):
            self._place(
                self._static_label(
                    self.grid_frame,
                    t("plate_header", self.lang, n=src),
                    bg=HEADER_BG,
                    fg=HEADER_FG,
                    font=("Helvetica", 12, "bold"),
                ),
                0, src,
            )

        self.start_label = self._static_label(
            self.grid_frame,
            t("start", self.lang),
            bg=ROW_LABEL_BG,
            fg=ROW_LABEL_FG,
            font=("Helvetica", 10, "bold"),
        )
        self._place(self.start_label, 1, 0)

        for src in range(1, num_plates + 1):
            var = tk.IntVar(value=TARGET)
            self.position_vars.append(var)
            self._place(self._make_position_cell(self.grid_frame, var), 1, src)

        for tgt in range(1, num_plates + 1):
            grid_row = tgt + 1
            arrow = self._static_label(
                self.grid_frame,
                t("influence_row", self.lang, n=tgt),
                bg=ROW_LABEL_BG,
                fg=ROW_LABEL_FG,
                font=("Helvetica", 10, "bold"),
            )
            self.arrow_labels.append(arrow)
            self._place(arrow, grid_row, 0)

            for src in range(1, num_plates + 1):
                if src == tgt:
                    self._place(
                        self._static_label(
                            self.grid_frame,
                            "—",
                            bg=DIAGONAL_BG,
                            fg="#ffffff",
                        ),
                        grid_row, src,
                    )
                    continue

                var = tk.IntVar(value=0)
                frame, lbl = self._make_influence_cell(self.grid_frame, var)
                self._place(frame, grid_row, src)
                self.influence_cells[(src, tgt)] = (var, lbl)

        self._layout_window()

    def _wheel_delta(self, event: tk.Event) -> int:
        if hasattr(event, "delta") and event.delta:
            return 1 if event.delta > 0 else -1
        if getattr(event, "num", None) == 4:
            return 1
        if getattr(event, "num", None) == 5:
            return -1
        return 0

    def _on_global_wheel(self, event: tk.Event) -> None:
        delta = self._wheel_delta(event)
        if not delta:
            return
        if self._influence_scroll is not None:
            var, lbl, frame = self._influence_scroll
            self.set_influence_value(var, lbl, frame, 1 if delta > 0 else -1)
        elif self._position_scroll is not None:
            self.bump_position(self._position_scroll, delta)

    def bump_position(self, var: tk.IntVar, delta: int) -> None:
        value = var.get() + delta
        var.set(max(MIN_POS, min(MAX_POS, value)))

    def set_influence_value(
        self, var: tk.IntVar, lbl: tk.Label, frame: tk.Frame, val: int
    ) -> None:
        var.set(val)
        text, bg, fg = INFLUENCE_STYLE[val]
        lbl.configure(text=text, bg=bg, fg=fg)
        frame.configure(bg=bg)

    def set_influence(self, src: int, tgt: int, sign: int) -> None:
        cell = self.influence_cells.get((src, tgt))
        if not cell:
            return
        var, lbl = cell
        self.set_influence_value(var, lbl, lbl.master, sign)

    def collect_positions(self) -> List[int]:
        positions = []
        for i, var in enumerate(self.position_vars):
            value = var.get()
            if not MIN_POS <= value <= MAX_POS:
                raise ValueError(
                    t("position_range", self.lang, n=i + 1, min=MIN_POS, max=MAX_POS)
                )
            positions.append(value)
        return positions

    def collect_influences(self) -> Dict[int, Dict[int, int]]:
        influences: Dict[int, Dict[int, int]] = {
            plate: {} for plate in range(1, self.num_plates + 1)
        }
        for (src, tgt), (var, _) in self.influence_cells.items():
            sign = var.get()
            if sign != 0:
                influences[src][tgt] = sign
        return influences

    def set_result_text(self, text: str) -> None:
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        if text:
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if ". " in line:
                    label, body = line.split(". ", 1)
                    self.result_text.insert(tk.END, label + ". ", "step_label")
                    self.result_text.insert(tk.END, body + "\n", "step_body")
                else:
                    self.result_text.insert(tk.END, line + "\n", "step_body")
        self.result_text.configure(state=tk.DISABLED)

    def reset_influences(self) -> None:
        for var, lbl in self.influence_cells.values():
            self.set_influence_value(var, lbl, lbl.master, 0)

    def reset_positions(self) -> None:
        for var in self.position_vars:
            var.set(TARGET)

    def on_clear_result(self) -> None:
        self.set_result_text("")
        self._last_solution = None
        self.reset_positions()
        self.reset_influences()
        self._set_status("ready")

    def on_load_example(self) -> None:
        self.rebuild_plate_fields(len(EXAMPLE_POSITIONS))
        for var, value in zip(self.position_vars, EXAMPLE_POSITIONS):
            var.set(value)
        for (src, tgt), sign in EXAMPLE_LINKS.items():
            self.set_influence(src, tgt, sign)
        self._last_solution = None
        self.set_result_text("")
        self._set_status("example_loaded")

    def on_solve(self) -> None:
        if self._solve_thread and self._solve_thread.is_alive():
            messagebox.showinfo(t("wait_title", self.lang), t("wait_body", self.lang))
            return

        try:
            config = PuzzleConfig(num_plates=self.num_plates)
            positions = self.collect_positions()
            influences = self.collect_influences()
        except ValueError as exc:
            messagebox.showerror(t("input_error", self.lang), str(exc))
            return

        lang = self.lang
        self.solve_btn.configure(state=tk.DISABLED)
        self._set_status("searching")
        self.set_result_text("")

        def worker() -> None:
            try:
                move_sequence, message = bfs_solve(positions, influences, config, lang=lang)
                if move_sequence is None:
                    self.root.after(0, lambda m=message: self._finish_solve(m, None, None))
                    return
                text = format_solution_text(positions, move_sequence, influences, config, lang)
                cache: SolveCache = (positions, move_sequence, influences)
                self.root.after(0, lambda m=message, t=text, c=cache: self._finish_solve(m, t, c))
            except Exception as exc:
                detail = t("error_prefix", lang, detail=exc)
                self.root.after(0, lambda d=detail: self._finish_solve(d, None, None))

        self._solve_thread = threading.Thread(target=worker, daemon=True)
        self._solve_thread.start()

    def _finish_solve(
        self,
        message: str,
        result_text: Optional[str],
        cache: Optional[SolveCache],
    ) -> None:
        self.solve_btn.configure(state=tk.NORMAL)
        if result_text:
            self._last_solution = cache
            self._set_status("ready")
            self.set_result_text(result_text)
        else:
            self._last_solution = None
            self.status_var.set(message)
            self.set_result_text(message)


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
    except tk.TclError:
        pass
    PlatePuzzleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
