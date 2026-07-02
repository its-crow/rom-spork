#!/usr/bin/env python3
"""
ROM‑SPORK – A retro‑style Windows desktop application to organize ROMs into a RetroDECK folder.
Author: ChatGPT
"""

import os
import shutil
import time
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --------------------------------------------------------------------------- #
# System mapping – extension → RetroDECK subfolder
EXT_SYSTEM_MAP = {
    ".nes": "nes",
    ".sfc": "snes",
    ".smc": "snes",
    ".gba": "gba",
    ".gb":  "gbc",
    ".gbc": "gbc",
    ".z64": "n64",
    ".n64": "n64",
    ".bin": "disc",   # generic disc – will be handled specially
    ".cue": "disc",
    ".gdi": "disc",
    ".iso": "disc",
    ".img": "disc",
    ".chd": "disc",
    ".mdf": "disc",
    ".cso": "disc",
    ".ccd": "disc",
    ".nrg": "disc",
}

# Parent folder name hints → system
PARENT_HINTS = {
    "nes":   "nes",
    "snes":  "snes",
    "gba":   "gba",
    "gbc":   "gbc",
    "n64":   "n64",
    "psx":   "psx",
    "playstation": "psx",
    "saturn": "saturn",
    "dreamcast": "dreamcast",
    "pcfx":  "pcfx",
}

# --------------------------------------------------------------------------- #
class ROMOrganizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ROM‑SPORK")
        self.geometry("800x600")
        self.configure(bg="#1e1e1e")

        # Variables
        self.source_dir = tk.StringVar()
        self.dest_dir   = tk.StringVar()

        # UI Elements
        self.create_widgets()

        # Progress tracking
        self.total_files = 0
        self.processed_files = 0
        self.start_time = None
        self.bytes_copied = 0

    def create_widgets(self):
        pad = {"padx": 10, "pady": 5}

        # Source selection
        src_frame = ttk.LabelFrame(self, text="Source Folder")
        src_frame.pack(fill="x", **pad)
        ttk.Entry(src_frame, textvariable=self.source_dir, width=80).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(src_frame, text="Browse…", command=self.browse_source).pack(side="right")

        # Destination selection
        dst_frame = ttk.LabelFrame(self, text="RetroDECK ROM Folder")
        dst_frame.pack(fill="x", **pad)
        ttk.Entry(dst_frame, textvariable=self.dest_dir, width=80).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(dst_frame, text="Browse…", command=self.browse_dest).pack(side="right")

        # Start button
        start_btn = ttk.Button(self, text="Start Organizing", command=self.start_organizing)
        start_btn.pack(pady=10)

        # Progress display
        progress_frame = ttk.LabelFrame(self, text="Progress")
        progress_frame.pack(fill="x", **pad)

        self.current_file_lbl = ttk.Label(progress_frame, text="Current file: ")
        self.current_file_lbl.pack(anchor="w")

        self.dest_path_lbl = ttk.Label(progress_frame, text="Destination: ")
        self.dest_path_lbl.pack(anchor="w")

        self.stats_lbl = ttk.Label(progress_frame, text="Processed 0 / 0")
        self.stats_lbl.pack(anchor="w")

        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", pady=5)

        self.speed_lbl = ttk.Label(progress_frame, text="Speed: N/A")
        self.speed_lbl.pack(anchor="e")

        # Report area
        report_frame = ttk.LabelFrame(self, text="Report")
        report_frame.pack(fill="both", expand=True, **pad)
        self.report_text = tk.Text(report_frame, wrap="none")
        self.report_text.pack(side="left", fill="both", expand=True)

        scrollbar_y = ttk.Scrollbar(report_frame, orient="vertical", command=self.report_text.yview)
        scrollbar_y.pack(side="right", fill="y")
        self.report_text.configure(yscrollcommand=scrollbar_y.set)

    def browse_source(self):
        path = filedialog.askdirectory(title="Select Source Folder")
        if path:
            self.source_dir.set(path)

    def browse_dest(self):
        path = filedialog.askdirectory(title="Select RetroDECK ROM Folder")
        if path:
            self.dest_dir.set(path)

    # ----------------------------------------------------------------------- #
    def start_organizing(self):
        src = Path(self.source_dir.get())
        dst = Path(self.dest_dir.get())

        if not src.is_dir():
            messagebox.showerror("Error", "Source folder does not exist.")
            return
        if not dst.is_dir():
            messagebox.showerror("Error", "Destination folder does not exist.")
            return

        # Disable UI during processing
        for child in self.winfo_children():
            child.configure(state="disabled")

        # Reset progress
        self.total_files = 0
        self.processed_files = 0
        self.bytes_copied = 0
        self.start_time = time.time()
        self.progress_bar["value"] = 0
        self.report_text.delete("1.0", tk.END)

        # Count total files first (for progress bar)
        for _ in src.rglob("*"):
            if _.is_file():
                self.total_files += 1

        # Start worker thread
        threading.Thread(target=self.organize_roms, args=(src, dst), daemon=True).start()

    def organize_roms(self, src: Path, dst: Path):
        copied = []
        skipped = []
        unknown = []
        errors = []
        duplicates = []

        for file_path in src.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(src)
            self.update_current_file(file_path.name)

            try:
                system = self.detect_system(file_path, src)
                if not system:
                    unknown.append(str(rel_path))
                    self.log_report(f"UNKNOWN: {rel_path}")
                    continue

                dest_subdir = dst / system
                dest_subdir.mkdir(parents=True, exist_ok=True)

                # Handle disc games specially
                if file_path.suffix.lower() in [".cue", ".gdi"]:
                    group_files = self.collect_disc_group(file_path)
                    for gfile in group_files:
                        dest_file = dest_subdir / gfile.name
                        if dest_file.exists():
                            duplicates.append(str(gfile.relative_to(src)))
                            self.log_report(f"DUPLICATE: {gfile.relative_to(src)}")
                            continue
                        try:
                            shutil.copy2(gfile, dest_file)
                            copied.append(str(gfile.relative_to(src)))
                            self.bytes_copied += gfile.stat().st_size
                            self.update_progress()
                        except Exception as e:
                            errors.append((str(gfile.relative_to(src)), str(e)))
                            self.log_report(f"ERROR: {gfile.relative_to(src)} – {e}")
                    continue

                # Regular file copy
                dest_file = dest_subdir / file_path.name
                if dest_file.exists():
                    duplicates.append(str(rel_path))
                    self.log_report(f"DUPLICATE: {rel_path}")
                    continue
                try:
                    shutil.copy2(file_path, dest_file)
                    copied.append(str(rel_path))
                    self.bytes_copied += file_path.stat().st_size
                    self.update_progress()
                except Exception as e:
                    errors.append((str(rel_path), str(e)))
                    self.log_report(f"ERROR: {rel_path} – {e}")

            except Exception as exc:
                errors.append((str(file_path.relative_to(src)), str(exc)))
                self.log_report(f"ERROR: {file_path.relative_to(src)} – {exc}")

        # Final report
        self.finalize_report(copied, skipped, unknown, errors, duplicates)

    def detect_system(self, file_path: Path, src_root: Path) -> str:
        ext = file_path.suffix.lower()
        if ext in EXT_SYSTEM_MAP:
            return EXT_SYSTEM_MAP[ext]

        # Check parent folder names for hints
        for part in file_path.parents:
            if part == src_root:
                break
            name_lower = part.name.lower()
            for hint, sys_name in PARENT_HINTS.items():
                if hint in name_lower:
                    return sys_name

        return None  # Unknown system

    def collect_disc_group(self, cue_file: Path):
        """
        Collect all files that belong to the same disc game.
        For simplicity, we consider any file in the same directory
        whose stem starts with the same base as the cue/gdi file.
        """
        base_stem = cue_file.stem.split()[0]  # take first token before space
        group = []
        for sibling in cue_file.parent.iterdir():
            if not sibling.is_file():
                continue
            if sibling.stem.startswith(base_stem):
                group.append(sibling)
        return group

    def update_current_file(self, filename: str):
        self.current_file_lbl.config(text=f"Current file: {filename}")

    def update_progress(self):
        self.processed_files += 1
        self.stats_lbl.config(
            text=f"Processed {self.processed_files} / {self.total_files}"
        )
        progress = (self.processed_files / self.total_files) * 100 if self.total_files else 0
        self.progress_bar["value"] = progress

        elapsed = time.time() - self.start_time
        speed_kb = (self.bytes_copied / 1024) / elapsed if elapsed > 0 else 0
        self.speed_lbl.config(text=f"Speed: {speed_kb:.2f} KB/s")

    def log_report(self, message: str):
        self.report_text.insert(tk.END, message + "\n")
        self.report_text.see(tk.END)

    def finalize_report(self, copied, skipped, unknown, errors, duplicates):
        # Re-enable UI
        for child in self.winfo_children():
            child.configure(state="normal")

        report = [
            "=== ROM‑SPORK Report ===",
            f"Copied files: {len(copied)}",
            f"Skipped files: {len(skipped)}",
            f"Unknown files: {len(unknown)}",
            f"Duplicate files: {len(duplicates)}",
            f"Errors: {len(errors)}",
        ]
        self.report_text.insert(tk.END, "\n".join(report) + "\n\n")

        if unknown:
            self.report_text.insert(tk.END, "Unknown Files:\n")
            for u in unknown:
                self.report_text.insert(tk.END, f"  - {u}\n")

        if duplicates:
            self.report_text.insert(tk.END, "\nDuplicate Files (skipped):\n")
            for d in duplicates:
                self.report_text.insert(tk.END, f"  - {d}\n")

        if errors:
            self.report_text.insert(tk.END, "\nErrors:\n")
            for err_path, err_msg in errors:
                self.report_text.insert(tk.END, f"  - {err_path}: {err_msg}\n")

        messagebox.showinfo("Done", "ROM organization complete. See report below.")

# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    app = ROMOrganizer()
    app.mainloop()
