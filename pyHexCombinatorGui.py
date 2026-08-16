#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# pyHexCombinatorGui v1.1
# Copyright (c) 2026 Suess Labs / Xeno Innovations, Inc.
# All rights reserved.
# Distributed under the terms of the MIT License

"""Tkinter GUI for combining Bootloader.hex and MainApp.hex.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pyHexCombinator import HexFileError, combine_hex_files


try:
  from tkinterdnd2 import DND_FILES, TkinterDnD

  BaseWindow = TkinterDnD.Tk
  DRAG_AND_DROP_AVAILABLE = True
except ImportError:
  BaseWindow = tk.Tk
  DND_FILES = None
  DRAG_AND_DROP_AVAILABLE = False

class HexCombinerApp:
  def __init__(self, root: tk.Tk) -> None:
    self.root = root
    self.root.title("PyHexCombinator GUI")
    self.root.minsize(620, 210)

    self.bootloader_path = tk.StringVar()
    self.mainapp_path = tk.StringVar()
    self.status = tk.StringVar(value=self._ready_message())

    self._build_ui()

  def _ready_message(self) -> str:
    if DRAG_AND_DROP_AVAILABLE:
      return "Ready"

    return "Ready - install tkinterdnd2 to enable drag and drop"

  def _build_ui(self) -> None:
    self.root.columnconfigure(0, weight=1)
    self.root.rowconfigure(0, weight=1)

    frame = ttk.Frame(self.root, padding=16)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(1, weight=1)

    self._add_file_row(frame, 0, "Bootloader", self.bootloader_path)
    self._add_file_row(frame, 1, "MainApp", self.mainapp_path)

    combine_button = ttk.Button(frame, text="Combine", command=self.combine)
    combine_button.grid(row=2, column=1, sticky="e", pady=(12, 8))

    status_label = ttk.Label(frame, textvariable=self.status, anchor="w")
    status_label.grid(row=3, column=0, columnspan=3, sticky="ew")

  def _add_file_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)

    entry = ttk.Entry(parent, textvariable=variable)
    entry.grid(row=row, column=1, sticky="ew", pady=6)
    self._enable_drop(entry, variable)

    browse_button = ttk.Button(parent, text="Browse", command=lambda: self._browse(variable))
    browse_button.grid(row=row, column=2, sticky="e", padx=(10, 0), pady=6)

  def _enable_drop(self, widget: ttk.Entry, variable: tk.StringVar) -> None:
    if not DRAG_AND_DROP_AVAILABLE:
      return

    widget.drop_target_register(DND_FILES)
    widget.dnd_bind("<<Drop>>", lambda event: self._handle_drop(event.data, variable))

  def _handle_drop(self, drop_data: str, variable: tk.StringVar) -> None:
    paths = self.root.tk.splitlist(drop_data)
    if not paths:
      return

    variable.set(str(Path(paths[0]).expanduser()))
    self.status.set("Ready")

  def _browse(self, variable: tk.StringVar) -> None:
    selected = filedialog.askopenfilename(
      title="Select Intel HEX file",
      filetypes=(("Intel HEX files", "*.hex *.HEX"), ("All files", "*.*")),
    )
    if selected:
      variable.set(selected)
      self.status.set("Ready")

  def combine(self) -> None:
    bootloader = self.bootloader_path.get().strip()
    mainapp = self.mainapp_path.get().strip()

    if not bootloader or not mainapp:
      messagebox.showerror("Missing file", "Select both Bootloader and MainApp HEX files.")
      return

    try:
      output = combine_hex_files(bootloader, mainapp)
    except HexFileError as exc:
      self.status.set("Combine failed")
      messagebox.showerror("Combine failed", str(exc))
      return
    except OSError as exc:
      self.status.set("Combine failed")
      messagebox.showerror("Combine failed", f"Could not write Combined.hex: {exc}")
      return

    self.status.set(f"Created {output}")
    messagebox.showinfo("Combine complete", f"Created:\n{output}")


def main() -> None:
  root = BaseWindow()
  HexCombinerApp(root)
  root.mainloop()


if __name__ == "__main__":
  main()
