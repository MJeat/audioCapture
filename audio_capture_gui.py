from __future__ import annotations

import datetime as dt
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from proctap import ProcessAudioCapture

from audio_capture_app import (
    AUDIO_DIR,
    TRANSCRIPT_DIR,
    MovAudioWriter,
    find_process_ids,
    transcribe_audio,
)


def safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return cleaned or "capture"


class AudioCaptureGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Audio Capture")
        self.root.resizable(False, False)

        self.target_var = tk.StringVar(value="chrome")
        self.name_var = tk.StringVar(value=f"capture_{dt.datetime.now():%Y%m%d_%H%M%S}")
        self.model_var = tk.StringVar(value="tiny")
        self.status_var = tk.StringVar(value="Ready")

        self.capture: ProcessAudioCapture | None = None
        self.writer: MovAudioWriter | None = None
        self.audio_path: Path | None = None
        self.transcript_path: Path | None = None
        self.selected_model = "tiny"
        self.paused = False
        self.stopping = False
        self.selected_model = self.model_var.get()
        self.capture_lock = threading.Lock()
        self.timer_var = tk.StringVar(value="00:00:00")
        self.started_at = 0.0
        self.paused_at = 0.0
        self.paused_total = 0.0
        self.timer_job: str | None = None

        self._build_widgets()
        self._bind_hotkeys()
        self._apply_theme()
        self.root.bind_all("<Button-1>", self._focus_clicked_widget, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _apply_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background="#18212b", foreground="#e8eef5", font=("Segoe UI", 10))
        style.configure("TFrame", background="#18212b")
        style.configure("TLabel", background="#18212b", foreground="#e8eef5")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 18), foreground="#79c7ff")
        style.configure("Timer.TLabel", font=("Consolas", 28, "bold"), foreground="#72e6a6")
        style.configure("Status.TLabel", foreground="#aebdca")
        style.configure("TButton", padding=(12, 7), background="#263646")
        style.map("TButton", background=[("active", "#36516a")])
        self.root.configure(background="#18212b")

    def _bind_hotkeys(self) -> None:
        self.root.bind_all("<KeyPress-1>", lambda _event: self.start())
        self.root.bind_all("<KeyPress-2>", lambda _event: self.toggle_pause())
        self.root.bind_all("<KeyPress-3>", lambda _event: self.stop())

    def _focus_clicked_widget(self, event: tk.Event[tk.Misc]) -> None:
        widget = event.widget
        if isinstance(widget, str):
            try:
                widget = self.root.nametowidget(widget)
            except KeyError:
                self.root.focus_set()
                return
        widget_class = widget.winfo_class()
        if widget_class not in {
            "Entry",
            "TEntry",
            "Combobox",
            "TCombobox",
            "Listbox",
        }:
            self.root.focus_set()

    def _build_widgets(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.grid()

        ttk.Label(frame, text="Audio Capture", style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, pady=(0, 8)
        )
        ttk.Label(frame, textvariable=self.timer_var, style="Timer.TLabel").grid(
            row=1, column=0, columnspan=3, pady=(0, 12)
        )
        ttk.Label(frame, text="Target process").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.target_var, width=32).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=4
        )
        ttk.Label(frame, text="File name").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.name_var, width=32).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=4
        )
        ttk.Label(frame, text="Whisper model").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frame,
            textvariable=self.model_var,
            values=("tiny", "base", "small"),
            state="readonly",
            width=29,
        ).grid(row=4, column=1, columnspan=2, sticky="ew", pady=4)
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, pady=(12, 6))
        self.record_button = ttk.Button(buttons, text="Record  [1]", command=self.start)
        self.record_button.grid(row=0, column=0, padx=4)
        self.pause_button = ttk.Button(
            buttons, text="Pause  [2]", command=self.toggle_pause, state="disabled"
        )
        self.pause_button.grid(row=0, column=1, padx=4)
        self.stop_button = ttk.Button(
            buttons, text="Stop  [3]", command=self.stop, state="disabled"
        )
        self.stop_button.grid(row=0, column=2, padx=4)
        ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel", wraplength=360).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

    def start(self) -> None:
        target = self.target_var.get().strip()
        if not target:
            messagebox.showerror("Missing target", "Enter a process name, such as chrome.")
            return
        process_ids = find_process_ids(target)
        if not process_ids:
            messagebox.showerror(
                "Process not found",
                f"No process matching {target!r} was found. Start it and try again.",
            )
            return

        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        base_name = safe_name(self.name_var.get())
        self.audio_path = AUDIO_DIR / f"{base_name}.mov"
        self.transcript_path = TRANSCRIPT_DIR / f"{base_name}.txt"
        self.writer = MovAudioWriter(self.audio_path)
        self.paused = False
        self.stopping = False
        self.selected_model = self.model_var.get()
        self.started_at = time.monotonic()
        self.paused_at = 0.0
        self.paused_total = 0.0
        self._update_timer()

        try:
            self.capture = ProcessAudioCapture(process_ids[0], on_data=self.on_audio)
            self.capture.start()
        except Exception:
            self.writer.close()
            self.writer = None
            self.capture = None
            raise

        self.record_button.configure(state="disabled")
        self.pause_button.configure(state="normal", text="Pause")
        self.stop_button.configure(state="normal")
        self.status_var.set(f"Recording PID {process_ids[0]} to {self.audio_path.name}")

    def on_audio(self, pcm_bytes: bytes, frame_count: int) -> None:
        if not self.paused and self.writer is not None:
            self.writer.write(pcm_bytes, frame_count)

    def toggle_pause(self) -> None:
        if self.capture is None:
            return
        self.paused = not self.paused
        if self.paused:
            self.paused_at = time.monotonic()
        else:
            self.paused_total += time.monotonic() - self.paused_at
        self.pause_button.configure(text="Resume  [2]" if self.paused else "Pause  [2]")
        self.status_var.set("Paused" if self.paused else f"Recording to {self.audio_path.name}")

    def stop(self) -> None:
        if self.capture is None or self.stopping:
            return
        self.stopping = True
        self.pause_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.status_var.set("Stopping and preparing transcript...")
        threading.Thread(target=self.finish_capture, daemon=True).start()

    def _update_timer(self) -> None:
        if self.started_at:
            paused_now = time.monotonic() - self.paused_at if self.paused else 0.0
            elapsed = max(
                0.0,
                time.monotonic() - self.started_at - self.paused_total - paused_now,
            )
            hours, remainder = divmod(int(elapsed), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.timer_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            self.timer_job = self.root.after(250, self._update_timer)

    def finish_capture(self) -> None:
        capture = self.capture
        writer = self.writer
        audio_path = self.audio_path
        transcript_path = self.transcript_path
        try:
            if capture is not None:
                capture.close()
            if writer is not None:
                writer.close()
            if writer is None or audio_path is None or transcript_path is None:
                raise RuntimeError("Capture was not initialized.")
            if writer.frames_written == 0 or writer.peak_level == 0:
                raise RuntimeError("No audible audio was captured.")
            transcribe_audio(audio_path, transcript_path, self.selected_model)
        except Exception as error:
            self.root.after(0, lambda: messagebox.showerror("Capture failed", str(error)))
            self.root.after(0, lambda: self.status_var.set("Capture failed"))
        else:
            self.root.after(
                0,
                lambda: self.status_var.set(
                    f"Saved audio and transcript as {audio_path.stem}"
                ),
            )
        finally:
            with self.capture_lock:
                self.capture = None
                self.writer = None
            self.root.after(0, self.reset_controls)

    def reset_controls(self) -> None:
        self.record_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Pause  [2]")
        self.stop_button.configure(state="disabled")
        self.stopping = False
        if self.timer_job is not None:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None

    def close(self) -> None:
        if self.capture is not None:
            self.stop()
            self.root.after(200, self.close)
            return
        self.root.destroy()


if __name__ == "__main__":
    app_root = tk.Tk()
    AudioCaptureGUI(app_root)
    app_root.mainloop()
