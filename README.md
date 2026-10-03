# Audio Capture App

Windows application-audio recorder that saves captured audio as `.mov` and
creates a local speech transcript as `.txt` using faster-whisper.

The recommended entry point is [main.ipynb](./main.ipynb), using the existing
conda Python 3.14.6 kernel. A virtual environment is not required.

## Quick start

1. Open [main.ipynb](./main.ipynb) in VS Code or Jupyter.
2. Select the conda `base` kernel running Python 3.14.6.
3. Run the setup cell.
4. Run the GUI launcher cell.
5. In the GUI, enter a target process such as `chrome`.
6. Click **Find processes** and select the Chrome process containing
   `audio.mojom.AudioService`.
7. Enter an output name.
8. Choose a Whisper model.
9. Click **Record**, then **Stop** when finished.

The application creates:

```text
audios\<name>.mov
transcripts\<name>.txt
```

## Detailed usage

### 1. Start the notebook

Open the project folder and open [main.ipynb](./main.ipynb). Use the existing
conda environment:

```text
C:\Users\USER\anaconda3\python.exe
```

Run the setup cell. It installs or verifies the packages listed in
[requirements.txt](./requirements.txt) inside the active notebook environment.

The setup cell also prints the Python interpreter and project path. Confirm
that the version is Python 3.14.6 and that the project path is correct.

### 2. Launch the GUI

Run the notebook cell titled **Launch the Tkinter GUI**. The GUI opens in a
separate window while the notebook remains available for process inspection.

The GUI can also be started directly after activating conda:

```powershell
conda activate base
python audio_capture_gui.py
```

### 3. Select the source process

The target process field expects a Windows process name, not a website title.
Common examples are:

| Application | Process name |
|---|---|
| Google Chrome | `chrome` |
| Microsoft Edge | `msedge` |
| Zoom | `zoom` |
| Discord | `discord` |
| Microsoft Teams | `teams` or `ms-teams` |

For YouTube or Google Meet, enter the browser process name, such as `chrome`.

#### Finding the correct Chrome process

Chrome normally has many processes. Do not select a random one.

1. Start the desired audio in Chrome.
2. Enter `chrome` in **Target process**.
3. Click **Find processes**.
4. Inspect the returned PID and command-line entries.
5. Prefer the entry containing:

   ```text
   audio.mojom.AudioService
   ```

6. Select that exact entry.
7. Keep the audio playing while recording.

The audio service is preferred because Chrome separates tabs, renderers, GPU
work, extensions, and audio into different processes. The visible browser
process is often not the process that owns the audio stream.

If there is no audio-service entry, test the highest-priority candidate with a
short recording. If the result is silent, refresh the list while audio is
playing and try another candidate.

Process IDs change when Chrome restarts, so refresh the list instead of reusing
an old PID.

The notebook also includes a process-inspection cell that prints matching PIDs,
process names, and command lines:

```python
from audio_capture_app import list_matching_processes

for pid, name, command_line in list_matching_processes("chrome"):
    print(f"PID {pid}: {name} | {command_line}")
```

### 4. Record audio

- **Record** starts capture.
- **Pause** temporarily stops writing incoming audio.
- **Resume** continues capture.
- **Stop** finalizes the `.mov` file and starts transcription.

The timer excludes paused time. The GUI displays a green confirmation after
the audio and transcript are saved. Errors and invalid inputs appear in the
red error panel instead of crashing the application.

### 5. Choose a Whisper model

- `tiny`: fastest, lowest resource use
- `base`: better accuracy, slower
- `small`: higher accuracy, slower and uses more memory

The selected model is downloaded and cached the first time it is used.
Transcription runs locally; audio is not sent to a transcription service.

### 6. Keyboard shortcuts

The default shortcuts are:

| Key | Action |
|---|---|
| `1` | Record |
| `2` | Pause or resume |
| `3` | Stop |

The shortcut fields can be changed in the GUI. Each shortcut must be a
single, unique key. See [KEY_BINDINGS.md](./KEY_BINDINGS.md) for details.

## Output files

Audio is saved to:

```text
audios\
```

Transcripts are saved to:

```text
transcripts\
```

The recorder produces QuickTime MOV files containing PCM audio. Existing audio
or transcript files are not overwritten; duplicate names are rejected before
recording starts.

## Troubleshooting

### The recording is silent

1. Confirm the source application is currently playing audio.
2. Click **Find processes** while the audio is playing.
3. Choose the process containing `audio.mojom.AudioService`.
4. Try a short recording.
5. If Chrome was restarted, refresh the process list because its PIDs changed.

### The target process cannot be found

Check the process name in Windows Task Manager:

1. Press `Ctrl+Shift+Esc`.
2. Open the **Details** tab.
3. Read the **Name** column.
4. Enter the name without `.exe`.

For example, use `chrome`, not `youtube.com`.

### The transcript says no speech was detected

The recording may contain music or silence rather than speech. Try the `base`
model for improved accuracy and ensure the source audio contains clear speech.

### A model-download warning appears

The first transcription may download a Whisper model from Hugging Face. The
model is cached locally afterward. Symlink and unauthenticated-download
messages are warnings, not application failures.

### A duplicate filename error appears

Change the output name or remove/archive the existing files in both `audios`
and `transcripts`. The app intentionally prevents accidental overwrites.

## Project files

| File | Purpose |
|---|---|
| [main.ipynb](./main.ipynb) | Recommended Jupyter entry point |
| [audio_capture_gui.py](./audio_capture_gui.py) | Tkinter GUI |
| [audio_capture_app.py](./audio_capture_app.py) | Capture, MOV encoding, and transcription logic |
| [MANUAL.md](./MANUAL.md) | Extended user manual |
| [TECHNICAL.md](./TECHNICAL.md) | Architecture and implementation details |
| [KEY_BINDINGS.md](./KEY_BINDINGS.md) | Shortcut configuration guide |
| [requirements.txt](./requirements.txt) | Python dependencies |
| `audios\` | Generated MOV recordings |
| `transcripts\` | Generated transcript files |

## Dependencies

The project uses:

- `proc-tap` for Windows process-specific audio capture
- `PyAV` for MOV encoding and decoding
- `numpy` and `scipy` for audio conversion and resampling
- `psutil` for process discovery
- `faster-whisper` for local transcription
- Tkinter for the GUI

Install or update them from the notebook setup cell, or manually with:

```powershell
conda activate base
python -m pip install -r requirements.txt
```
