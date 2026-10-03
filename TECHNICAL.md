# Technical Explanation

## Project components

| File | Responsibility |
|---|---|
| [audio_capture_app.py](./audio_capture_app.py) | Core process selection, audio capture, MOV encoding, and transcription |
| [audio_capture_gui.py](./audio_capture_gui.py) | Tkinter user interface that controls the core capture functions |
| [main.ipynb](./main.ipynb) | Primary conda/Jupyter entry point and GUI launcher |
| [requirements.txt](./requirements.txt) | Python dependencies |
| `audios\` | Default `.mov` output folder |
| `transcripts\` | Default transcript output folder |

## Audio capture pipeline

The core application uses `proc-tap`:

```python
ProcessAudioCapture(process_id, on_data=callback)
```

On Windows, `proc-tap` uses WASAPI process loopback. Its standard output format is:

- Sample rate: `48000 Hz`
- Channels: `2`
- Sample format: `float32`
- Normalized sample range: approximately `-1.0` to `1.0`

The callback receives:

```python
callback(pcm_bytes, frame_count)
```

The current backend does not provide a reliable frame count, so the writer derives the number of frames from the byte payload.

## MOV writer

`MovAudioWriter` converts each incoming float32 chunk to signed 16-bit PCM:

1. Interpret the bytes as float32 samples.
2. Clip samples to `[-1.0, 1.0]`.
3. Scale to the int16 range.
4. Create an `av.AudioFrame`.
5. Assign a presentation timestamp based on total frames already written.
6. Encode with the `pcm_s16le` codec inside a QuickTime MOV container.

The timestamps are important. Without them, a long recording can be decoded as only a few milliseconds even though the file is large.

The writer also tracks:

- `frames_written`
- `peak_level`

These values are used to reject empty or silent captures.

## Process selection

`find_process_ids()` scans accessible processes by name and command line. Matches are sorted to prioritize likely audio-producing processes.

For Chromium-based browsers, the audio service process commonly contains:

```text
--utility-sub-type=audio.mojom.AudioService
```

The command-line app can capture one exact PID with `--pid`. By default, it captures the highest-priority matching process rather than every browser process.

## Transcription pipeline

`transcribe_audio()` uses `faster-whisper` locally:

1. Open the completed MOV with PyAV.
2. Decode audio frames.
3. Convert signed 16-bit samples to normalized float32.
4. Convert stereo to mono.
5. Downsample from 48 kHz to 16 kHz by taking every third sample.
6. Load the selected Whisper model on the CPU using int8 computation.
7. Transcribe with voice activity detection enabled.
8. Write the language and transcript to a text file.

The default model is `tiny`. Larger models generally improve accuracy but require more download time, memory, and CPU time.

Transcript sentences ending in a period are placed on separate indented lines using:

```python
re.split(r"(?<=\.)\s+", text)
```

This is intentionally simple and does not split on question marks or exclamation marks.

## GUI architecture

### Jupyter and conda entry point

The notebook is intended to be the normal user-facing launch path. It installs
`requirements.txt` into the active conda kernel, adds the project directory to
`sys.path`, and starts the GUI with `sys.executable`. This guarantees that the
GUI uses the same Python 3.14.6 interpreter selected by Jupyter. The GUI still
runs as a separate Tkinter process so the notebook kernel remains responsive.

`AudioCaptureGUI` is a Tkinter controller around the core application.

### Recording

When Record is clicked:

1. The target process is resolved.
2. The output directories are created.
3. A `MovAudioWriter` is created.
4. `ProcessAudioCapture` starts in callback mode.
5. The timer starts.
6. The Record button is disabled and Pause/Stop are enabled.

The capture callback runs in `proc-tap`'s worker thread. While not paused, it forwards data to `MovAudioWriter`.

### Pause

Pause does not stop the process loopback backend. It prevents incoming callback chunks from being written to the MOV file. The timer subtracts paused time from displayed elapsed time.

### Stop and transcription

Stop starts `finish_capture()` on a background thread so the Tkinter event loop remains responsive while:

1. The capture is closed.
2. The MOV stream is flushed and closed.
3. Silent/empty output is checked.
4. Whisper transcription runs.
5. The GUI status is updated with `root.after(...)`.

Tkinter widget updates are kept on the GUI thread.

### Keyboard shortcuts

The GUI uses `bind_all()`:

```python
<KeyPress-1> -> start()
<KeyPress-2> -> toggle_pause()
<KeyPress-3> -> stop()
```

The click-focus handler resolves Tk widget path strings with `nametowidget()` before checking the widget class. This prevents errors when Tk sends a widget path instead of a widget instance and avoids interfering with dropdown controls.

## Output naming

The GUI writes:

```text
audios\<base-name>.mov
transcripts\<base-name>.txt
```

The command-line app generates timestamped names:

```text
capture_YYYYMMDD_HHMMSS.mov
capture_YYYYMMDD_HHMMSS.txt
```

`safe_name()` replaces invalid Windows filename characters before creating output paths.

## Dependency roles

| Dependency | Role |
|---|---|
| `proc-tap` | Windows process-specific audio capture |
| `PyAV` (`av`) | MOV container and audio frame encoding/decoding |
| `numpy` | PCM conversion, clipping, channel mixing, and resampling |
| `psutil` | Process discovery |
| `faster-whisper` | Local speech-to-text |
| `tkinter` | GUI, included with standard Windows Python installations |

## Extension points

Potential future improvements include:

- Resampling with a quality-controlled audio resampler instead of simple decimation
- Sentence formatting for `?` and `!`
- Selecting a process from a GUI list
- Selecting an exact PID in the GUI
- GPU Whisper support
- Live partial transcription while recording
- Persistent GUI preferences
