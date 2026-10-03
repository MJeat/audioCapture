from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import signal
import time
from pathlib import Path
from threading import Event, Lock
from typing import Optional

import av
import numpy as np
import psutil
from proctap import ProcessAudioCapture


SAMPLE_RATE = 48_000
CHANNELS = 2
PROJECT_DIR = Path(__file__).resolve().parent
AUDIO_DIR = PROJECT_DIR / "audios"
TRANSCRIPT_DIR = PROJECT_DIR / "transcripts"


def find_process_ids(search_text: str) -> list[int]:
    """Return matching processes, prioritizing processes that own audio output."""
    needle = search_text.casefold()
    matches: list[tuple[int, str]] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (process.info["name"] or "").casefold()
            command_line = " ".join(process.info["cmdline"] or []).casefold()
            if needle in name or needle in command_line:
                matches.append((int(process.info["pid"]), command_line))
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    matches.sort(
        key=lambda item: (
            "audio.mojom.audioservice" not in item[1],
            "--type=renderer" in item[1],
            "--type=crashpad-handler" in item[1],
        )
    )
    return [pid for pid, _ in matches]


class MovAudioWriter:
    """Write proc-tap's float32 stereo PCM chunks to a QuickTime MOV file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.container = av.open(str(path), mode="w", format="mov")
        self.stream = self.container.add_stream("pcm_s16le", rate=SAMPLE_RATE)
        self.stream.layout = "stereo"
        self._lock = Lock()
        self._closed = False
        self.frames_written = 0
        self.peak_level = 0.0

    def write(self, pcm_bytes: bytes, frame_count: int) -> None:
        del frame_count  # The byte payload is the authoritative chunk size.
        if not pcm_bytes:
            return
        samples = np.frombuffer(pcm_bytes, dtype=np.float32)
        if samples.size % CHANNELS:
            raise ValueError(
                f"Received {samples.size} float samples, which is not divisible "
                f"by {CHANNELS} channels."
            )
        self.peak_level = max(self.peak_level, float(np.max(np.abs(samples))))
        clipped = np.clip(samples, -1.0, 1.0)
        packed = np.rint(clipped * np.iinfo(np.int16).max).astype(np.int16)
        with self._lock:
            frame_pts = self.frames_written
        frame = av.AudioFrame.from_ndarray(
            packed.reshape(1, -1), format="s16", layout="stereo"
        )
        frame.sample_rate = SAMPLE_RATE
        frame.pts = frame_pts
        with self._lock:
            if self._closed:
                return
            for packet in self.stream.encode(frame):
                self.container.mux(packet)
            self.frames_written += samples.size // CHANNELS

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            for packet in self.stream.encode():
                self.container.mux(packet)
            self.container.close()
            self._closed = True


def transcribe_audio(audio_path: Path, transcript_path: Path, model_name: str) -> None:
    """Transcribe the MOV locally with faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError(
            "Transcription requires faster-whisper. Run: "
            "python -m pip install faster-whisper"
        ) from error

    container = av.open(str(audio_path))
    stream = container.streams.audio[0]
    chunks: list[np.ndarray] = []
    for frame in container.decode(stream):
        data = frame.to_ndarray().astype(np.float32) / np.iinfo(np.int16).max
        if data.ndim == 2 and data.shape[0] == CHANNELS:
            data = data.mean(axis=0)
        elif data.ndim == 2:
            data = data.reshape(-1, CHANNELS).mean(axis=1)
        chunks.append(data)
    container.close()
    if not chunks:
        transcript_path.write_text("No audio frames were captured.\n", encoding="utf-8")
        return

    audio = np.concatenate(chunks)
    audio = audio[::3]  # 48 kHz -> 16 kHz, the format expected by Whisper.
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio, vad_filter=True)
    lines = [f"Language: {info.language}", ""]
    text = " ".join(segment.text.strip() for segment in segments).strip()
    if text:
        sentences = re.split(r"(?<=\.)\s+", text)
        lines.extend(f"    {sentence.strip()}" for sentence in sentences if sentence.strip())
    else:
        lines.append("[No speech detected]")
    transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def record(
    target: str,
    duration: Optional[float],
    process_id: Optional[int] = None,
    all_processes: bool = False,
    transcribe: bool = True,
    model_name: str = "tiny",
) -> tuple[Path, Path]:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    process_ids = [process_id] if process_id is not None else find_process_ids(target)
    if not process_ids:
        raise RuntimeError(
            f"Could not find an active process matching {target!r}. "
            "Open the app and make sure it is playing audio."
        )
    if not all_processes:
        process_ids = process_ids[:1]
    print(f"Selected process IDs: {', '.join(map(str, process_ids))}")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = AUDIO_DIR / f"capture_{timestamp}.mov"
    transcript_path = TRANSCRIPT_DIR / f"capture_{timestamp}.txt"
    writer = MovAudioWriter(audio_path)
    stop_event = Event()
    started_at = time.monotonic()

    def stop_handler(signum: int, frame: object) -> None:
        del signum, frame
        stop_event.set()

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, stop_handler)
    captures: list[ProcessAudioCapture] = []
    try:
        captures = [ProcessAudioCapture(pid, on_data=writer.write) for pid in process_ids]
        for capture in captures:
            capture.start()
        print(f"Capturing {len(captures)} matching process(es) ({target!r}) to {audio_path}")
        print("Press Ctrl+C to stop.")
        while not stop_event.wait(0.25):
            if duration is not None and time.monotonic() - started_at >= duration:
                break
    finally:
        for capture in captures:
            capture.close()
        signal.signal(signal.SIGINT, previous_handler)
        writer.close()

    if writer.frames_written == 0 or writer.peak_level == 0:
        raise RuntimeError(
            "The capture contains no audible samples. Make sure the target is "
            "playing audio, or pass --pid for the process shown by --list."
        )
    if transcribe:
        print(f"Transcribing with faster-whisper model {model_name!r}...")
        transcribe_audio(audio_path, transcript_path, model_name)
    else:
        transcript_path.write_text(
            "Transcription disabled. Run again without --no-transcribe.\n",
            encoding="utf-8",
        )
    print(f"Saved {writer.frames_written} frames to {audio_path}")
    print(f"Transcript sidecar: {transcript_path}")
    return audio_path, transcript_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture one Windows app's audio.")
    parser.add_argument(
        "--target",
        default=os.environ.get("TARGET_APP", "chrome"),
        help="Process name or command-line text to capture (default: chrome).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Stop automatically after this many seconds.",
    )
    parser.add_argument("--pid", type=int, help="Capture one exact process ID.")
    parser.add_argument(
        "--all-processes",
        action="store_true",
        help="Capture every matching process (usually unnecessary for browsers).",
    )
    parser.add_argument(
        "--list-processes",
        action="store_true",
        help="List matching processes and exit.",
    )
    parser.add_argument(
        "--no-transcribe",
        action="store_true",
        help="Skip local Whisper transcription.",
    )
    parser.add_argument(
        "--model",
        default="tiny",
        help="faster-whisper model (tiny, base, small; default: tiny).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        if arguments.list_processes:
            for pid in find_process_ids(arguments.target):
                process = psutil.Process(pid)
                print(f"{pid}: {process.name()}")
            raise SystemExit(0)
        record(
            arguments.target,
            arguments.duration,
            process_id=arguments.pid,
            all_processes=arguments.all_processes,
            transcribe=not arguments.no_transcribe,
            model_name=arguments.model,
        )
    except KeyboardInterrupt:
        print("\nCapture stopped.")
    except Exception as error:
        raise SystemExit(f"Capture failed: {error}") from error
