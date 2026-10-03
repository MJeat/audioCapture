from __future__ import annotations

import datetime as dt
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

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
        self.record_key_var = tk.StringVar(value="1")
        self.pause_key_var = tk.StringVar(value="2")
        self.stop_key_var = tk.StringVar(value="3")
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
        self.bound_sequences: set[str] = set()
        self.status_frame: ttk.Frame
        self.status_label: ttk.Label

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
        style.configure("Input.TEntry", fieldbackground="#3b2d1c", foreground="#ffb347")
        style.configure("Input.TCombobox", fieldbackground="#3b2d1c", foreground="#ffb347")
        style.map(
            "Input.TCombobox",
            fieldbackground=[("readonly", "#3b2d1c")],
            foreground=[("readonly", "#ffb347")],
        )
        style.configure(
            "Saved.TFrame", background="#163b25", relief="solid", borderwidth=1
        )
        style.configure("Saved.TLabel", background="#163b25", foreground="#b9f6c9")
        style.configure(
            "Error.TFrame", background="#4a1f25", relief="solid", borderwidth=1
        )
        style.configure("Error.TLabel", background="#4a1f25", foreground="#ffb8bd")
        style.configure("TButton", padding=(12, 7), background="#263646")
        style.map("TButton", background=[("active", "#36516a")])
        self.root.configure(background="#18212b")

    def _bind_hotkeys(self) -> None:
        self._refresh_hotkeys()

    def _refresh_hotkeys(self) -> None:
        for sequence in self.bound_sequences:
            self.root.unbind_all(sequence)
        self.bound_sequences.clear()
        for key, callback in (
            (self.record_key_var.get(), self.start),
            (self.pause_key_var.get(), self.toggle_pause),
            (self.stop_key_var.get(), self.stop),
        ):
            if key.strip():
                sequence = f"<KeyPress-{key.strip()}>"
                try:
                    self.root.bind_all(
                        sequence, lambda _event, action=callback: action()
                    )
                except tk.TclError:
                    continue
                self.bound_sequences.add(sequence)
        if hasattr(self, "record_button"):
            self.record_button.configure(text=f"Record  [{self.record_key_var.get()}]")
            self.pause_button.configure(text=f"Pause  [{self.pause_key_var.get()}]")
            self.stop_button.configure(text=f"Stop  [{self.stop_key_var.get()}]")

    def _focus_clicked_widget(self, event: tk.Event[tk.Misc]) -> None:
        widget = event.widget
        if isinstance(widget, str):
            # Combobox popups are temporary Tk widgets and cannot always be
            # resolved with nametowidget. Never steal their focus.
            widget_path = widget.lower()
            if "popdown" in widget_path or "combobox" in widget_path:
                return
            try:
                widget = self.root.nametowidget(widget)
            except KeyError:
                return
        if widget.winfo_class() not in {
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
        ttk.Entry(frame, textvariable=self.target_var, style="Input.TEntry", width=32).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=4
        )
        ttk.Label(frame, text="File name").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.name_var, style="Input.TEntry", width=32).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=4
        )
        ttk.Label(frame, text="Whisper model").grid(row=4, column=0, sticky="w", pady=4)
        self.model_combo = ttk.Combobox(
            frame,
            textvariable=self.model_var,
            values=("tiny", "base", "small"),
            state="readonly",
            width=29,
        )
        self.model_combo.configure(style="Input.TCombobox")
        self.model_combo.grid(row=4, column=1, columnspan=2, sticky="ew", pady=4)
        self.model_combo.bind("<<ComboboxSelected>>", self._model_selected)
        ttk.Label(frame, text="Shortcuts").grid(row=5, column=0, sticky="w", pady=4)
        shortcut_frame = ttk.Frame(frame)
        shortcut_frame.grid(row=5, column=1, columnspan=2, sticky="ew", pady=4)
        for column, label, variable in (
            (0, "Record", self.record_key_var),
            (1, "Pause", self.pause_key_var),
            (2, "Stop", self.stop_key_var),
        ):
            ttk.Label(shortcut_frame, text=label).grid(row=0, column=column, padx=2)
            entry = ttk.Entry(
                shortcut_frame, textvariable=variable, style="Input.TEntry", width=7
            )
            entry.grid(row=1, column=column, padx=2)
            entry.bind("<KeyRelease>", lambda _event: self._refresh_hotkeys())
        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=3, pady=(12, 6))
        self.record_button = ttk.Button(
            buttons, text=f"Record  [{self.record_key_var.get()}]", command=self.start
        )
        self.record_button.grid(row=0, column=0, padx=4)
        self.pause_button = ttk.Button(
            buttons, text=f"Pause  [{self.pause_key_var.get()}]", command=self.toggle_pause, state="disabled"
        )
        self.pause_button.grid(row=0, column=1, padx=4)
        self.stop_button = ttk.Button(
            buttons, text=f"Stop  [{self.stop_key_var.get()}]", command=self.stop, state="disabled"
        )
        self.stop_button.grid(row=0, column=2, padx=4)
        self.status_frame = ttk.Frame(frame, style="Saved.TFrame", padding=10)
        self.status_frame.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.status_label = ttk.Label(
            self.status_frame,
            textvariable=self.status_var,
            style="Saved.TLabel",
            wraplength=500,
        )
        self.status_label.grid(row=0, column=0, sticky="w")

    def _model_selected(self, _event: object) -> None:
        self.show_status(f"Selected Whisper model: {self.model_var.get()}")

    def show_status(self, message: str) -> None:
        self.status_frame.configure(style="Saved.TFrame")
        self.status_label.configure(style="Saved.TLabel")
        self.status_var.set(message)

    def show_error(self, message: str) -> None:
        self.status_frame.configure(style="Error.TFrame")
        self.status_label.configure(style="Error.TLabel")
        self.status_var.set(f"ERROR\n{message}")

    def start(self) -> None:
        target = self.target_var.get().strip()
        if not target:
            self.show_error("Target process is empty. Enter a process name such as chrome.")
            return
        name = self.name_var.get().strip()
        if not name:
            self.show_error("File name is empty. Enter a name for the recording.")
            return
        if self.model_var.get() not in {"tiny", "base", "small"}:
            self.show_error("Choose a Whisper model from the dropdown.")
            return
        shortcut_keys = [
            self.record_key_var.get().strip(),
            self.pause_key_var.get().strip(),
            self.stop_key_var.get().strip(),
        ]
        if any(len(key) != 1 for key in shortcut_keys) or len(set(shortcut_keys)) != 3:
            self.show_error(
                "Record, Pause, and Stop shortcuts must each be different single keys."
            )
            return
        process_ids = find_process_ids(target)
        if not process_ids:
            self.show_error(
                f"Target process '{target}' was not found. Start the app and verify "
                "its process name in Task Manager.",
            )
            return

        try:
            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
            base_name = safe_name(name)
            self.audio_path = AUDIO_DIR / f"{base_name}.mov"
            self.transcript_path = TRANSCRIPT_DIR / f"{base_name}.txt"
            existing_files = [
                str(path)
                for path in (self.audio_path, self.transcript_path)
                if path.exists()
            ]
            if existing_files:
                self.show_error(
                    "A file with this recording name already exists:\n"
                    + "\n".join(existing_files)
                    + "\nChoose a different file name."
                )
                return
            self.writer = MovAudioWriter(self.audio_path)
        except Exception as error:
            self.show_error(f"Could not prepare output files: {error}")
            self.writer = None
            return
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
        except Exception as error:
            if self.writer is not None:
                self.writer.close()
            self.writer = None
            self.capture = None
            self.show_error(f"Could not start audio capture: {error}")
            return

        self.record_button.configure(state="disabled")
        self.pause_button.configure(state="normal", text="Pause  [2]")
        self.stop_button.configure(state="normal")
        self.show_status(f"Recording PID {process_ids[0]} to {self.audio_path.name}")

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
        self.show_status("Paused" if self.paused else f"Recording to {self.audio_path.name}")

    def stop(self) -> None:
        if self.capture is None or self.stopping:
            return
        self.stopping = True
        self.pause_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.show_status("Stopping and preparing transcript...")
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
            self.root.after(0, lambda: self.show_error(f"Capture failed: {error}"))
        else:
            self.root.after(
                0,
                lambda: self.show_status(
                    f"The Audio is saved:\n{audio_path}\n\n"
                    f"The Transcript is saved:\n{transcript_path}"
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
