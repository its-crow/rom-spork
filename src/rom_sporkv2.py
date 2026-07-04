#!/usr/bin/env python3
"""
ROM-SPORK v2 - Retro ROM organizer for RetroDECK
Retro terminal UI + safe threaded processing
"""

import os
import shutil
import time
import threading
import queue
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox

# ------------------------- SYSTEM MAP ------------------------- #

EXT_SYSTEM_MAP = {
    ".nes": "nes",
    ".sfc": "snes",
    ".smc": "snes",
    ".gba": "gba",
    ".gb": "gbc",
    ".gbc": "gbc",
    ".z64": "n64",
    ".n64": "n64",
    ".cue": "disc",
    ".gdi": "disc",
    ".iso": "disc",
    ".chd": "disc",
}

PARENT_HINTS = {
    "nes": "nes",
    "snes": "snes",
    "gba": "gba",
    "gbc": "gbc",
    "n64": "n64",
    "psx": "psx",
    "playstation": "psx",
    "dreamcast": "dreamcast",
}

# ------------------------- APP ------------------------- #

class ROMSpork(ctk.CTk):

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("ROM-SPORK // RetroDECK Sync")
        self.geometry("900x650")

        self.configure(bg="#050805")

        # state
        self.src = ctk.StringVar()
        self.dst = ctk.StringVar()

        self.q = queue.Queue()
        self.total = 0
        self.done = 0
        self.bytes_copied = 0
        self.start_time = 0

        self.worker_running = False

        self._build_ui()
        self.after(100, self._poll_queue)

    # ---------------- UI ---------------- #

    def _build_ui(self):

        self.title_lbl = ctk.CTkLabel(
            self,
            text="ROM-SPORK TERMINAL v2",
            font=("Courier", 20, "bold"),
            text_color="#33ff66"
        )
        self.title_lbl.pack(pady=10)

        # Source
        self.src_entry = ctk.CTkEntry(self, textvariable=self.src, width=700)
        self.src_entry.pack(pady=5)

        self.src_btn = ctk.CTkButton(self, text="Select ROM Source", command=self.pick_src)
        self.src_btn.pack(pady=5)

        # Dest
        self.dst_entry = ctk.CTkEntry(self, textvariable=self.dst, width=700)
        self.dst_entry.pack(pady=5)

        self.dst_btn = ctk.CTkButton(self, text="Select RetroDECK Folder", command=self.pick_dst)
        self.dst_btn.pack(pady=5)

        # Start
        self.start_btn = ctk.CTkButton(
            self,
            text="EXECUTE ORGANIZE",
            fg_color="#1f6f3a",
            hover_color="#2ecc71",
            command=self.start
        )
        self.start_btn.pack(pady=15)

        # progress
        self.progress = ctk.CTkProgressBar(self, width=700)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.status = ctk.CTkLabel(self, text="Idle", text_color="#33ff66")
        self.status.pack()

        # log box (retro terminal)
        self.log = ctk.CTkTextbox(
            self,
            width=850,
            height=350,
            font=("Courier", 12)
        )
        self.log.pack(pady=10)
        self._log("SYSTEM READY")

    # ---------------- helpers ---------------- #

    def _log(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def pick_src(self):
        path = filedialog.askdirectory()
        if path:
            self.src.set(path)

    def pick_dst(self):
        path = filedialog.askdirectory()
        if path:
            self.dst.set(path)

    # ---------------- start ---------------- #

    def start(self):

        if self.worker_running:
            return

        src = Path(self.src.get())
        dst = Path(self.dst.get())

        if not src.exists() or not dst.exists():
            messagebox.showerror("Error", "Invalid folders")
            return

        self.log.delete("1.0", "end")
        self._log("SCANNING...")

        self.worker_running = True
        self.done = 0
        self.bytes_copied = 0
        self.start_time = time.time()

        self.worker = threading.Thread(target=self._worker, args=(src, dst), daemon=True)
        self.worker.start()

    # ---------------- worker ---------------- #

    def _detect_system(self, file_path: Path):
        ext = file_path.suffix.lower()

        if ext in EXT_SYSTEM_MAP:
            return EXT_SYSTEM_MAP[ext]

        for parent in file_path.parents:
            for k, v in PARENT_HINTS.items():
                if k in parent.name.lower():
                    return v
        return None

    def _worker(self, src: Path, dst: Path):

        files = [p for p in src.rglob("*") if p.is_file()]
        self.total = len(files)

        self.q.put(("log", f"FOUND {self.total} FILES"))

        for f in files:

            system = self._detect_system(f)

            if not system:
                self.q.put(("log", f"UNKNOWN: {f.name}"))
                self._step()
                continue

            out_dir = dst / system
            out_dir.mkdir(parents=True, exist_ok=True)

            target = out_dir / f.name

            try:
                if not target.exists():
                    shutil.copy2(f, target)
                    self.bytes_copied += f.stat().st_size
                    self.q.put(("log", f"COPIED → {system}/{f.name}"))
                else:
                    self.q.put(("log", f"SKIP DUP → {f.name}"))

            except Exception as e:
                self.q.put(("log", f"ERROR {f.name}: {e}"))

            self._step()

        self.q.put(("done", None))

    def _step(self):
        self.done += 1
        self.q.put(("progress", self.done / self.total if self.total else 1))

    # ---------------- queue UI thread ---------------- #

    def _poll_queue(self):

        try:
            while True:
                msg, data = self.q.get_nowait()

                if msg == "log":
                    self._log(data)

                elif msg == "progress":
                    self.progress.set(data)
                    self.status.configure(text=f"{self.done}/{self.total}")

                elif msg == "done":
                    self.worker_running = False
                    self._log("DONE.")
                    self.status.configure(text="COMPLETE")

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app = ROMSpork()
    app.mainloop()